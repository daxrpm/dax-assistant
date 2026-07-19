package com.dax.assistant.audio

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import com.dax.assistant.core.log.DaxLog
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.flow.flowOn
import kotlinx.coroutines.Dispatchers

/** What the recognizer reports while a turn is in progress. */
sealed interface RecognitionEvent {
    data object ReadyForSpeech : RecognitionEvent
    data object SpeechStarted : RecognitionEvent
    data class Partial(val text: String) : RecognitionEvent
    data class Final(val text: String) : RecognitionEvent
    data class Failed(val reason: String, val recoverable: Boolean) : RecognitionEvent
}

/**
 * Speech to text, on-device when the platform can.
 *
 * On-device recognition is preferred for the obvious reason — the audio never
 * leaves the phone — and a practical one: it is materially faster than a round
 * trip, and latency is what makes a voice assistant feel alive or broken.
 * Availability is checked at runtime rather than assumed, because it depends on
 * which speech services the ROM ships and which language packs are installed;
 * HyperOS is not AOSP here.
 *
 * When on-device is unavailable this still works — Android falls back to the
 * networked recognizer. Callers that need audio to stay local must check
 * [onDeviceAvailable] and route to the backend's own STT instead.
 */
class SpeechRecognition(private val context: Context) {

    val isAvailable: Boolean
        get() = SpeechRecognizer.isRecognitionAvailable(context)

    val onDeviceAvailable: Boolean
        get() = runCatching { SpeechRecognizer.isOnDeviceRecognitionAvailable(context) }
            .getOrDefault(false)

    /**
     * Runs one recognition turn.
     *
     * The recognizer must be created and driven on the main looper, which is
     * why this is a callbackFlow rather than a suspend function: it bridges a
     * main-thread callback API into structured concurrency, and cancelling the
     * collector tears the recognizer down.
     */
    fun listen(languageTag: String, preferOnDevice: Boolean = true): Flow<RecognitionEvent> =
        callbackFlow {
            if (!isAvailable) {
                trySend(RecognitionEvent.Failed("Speech recognition unavailable", false))
                close()
                return@callbackFlow
            }

            val useOnDevice = preferOnDevice && onDeviceAvailable
            val recognizer = if (useOnDevice) {
                SpeechRecognizer.createOnDeviceSpeechRecognizer(context)
            } else {
                SpeechRecognizer.createSpeechRecognizer(context)
            }

            val listener = object : RecognitionListener {
                override fun onReadyForSpeech(params: Bundle?) {
                    trySend(RecognitionEvent.ReadyForSpeech)
                }

                override fun onBeginningOfSpeech() {
                    trySend(RecognitionEvent.SpeechStarted)
                }

                override fun onPartialResults(partialResults: Bundle?) {
                    partialResults
                        ?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                        ?.firstOrNull()
                        ?.takeIf { it.isNotBlank() }
                        ?.let { trySend(RecognitionEvent.Partial(it)) }
                }

                override fun onResults(results: Bundle?) {
                    val text = results
                        ?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                        ?.firstOrNull()
                        .orEmpty()
                    trySend(RecognitionEvent.Final(text))
                    close()
                }

                override fun onError(error: Int) {
                    val (reason, recoverable) = describe(error)
                    DaxLog.d(TAG, "Recognition error $error: $reason")
                    trySend(RecognitionEvent.Failed(reason, recoverable))
                    close()
                }

                override fun onEndOfSpeech() = Unit
                override fun onRmsChanged(rmsdB: Float) = Unit
                override fun onBufferReceived(buffer: ByteArray?) = Unit
                override fun onEvent(eventType: Int, params: Bundle?) = Unit
            }

            recognizer.setRecognitionListener(listener)
            recognizer.startListening(
                Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                    putExtra(
                        RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                        RecognizerIntent.LANGUAGE_MODEL_FREE_FORM,
                    )
                    putExtra(RecognizerIntent.EXTRA_LANGUAGE, languageTag)
                    putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
                    // Endpointing is left to the platform. It has the acoustic
                    // model and knows when a sentence ended; a fixed timer here
                    // would cut people off mid-thought.
                    putExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE, useOnDevice)
                },
            )

            awaitClose {
                runCatching {
                    recognizer.stopListening()
                    recognizer.destroy()
                }
            }
        }.flowOn(Dispatchers.Main)

    private fun describe(error: Int): Pair<String, Boolean> = when (error) {
        SpeechRecognizer.ERROR_NO_MATCH -> "I didn't catch that" to true
        SpeechRecognizer.ERROR_SPEECH_TIMEOUT -> "I didn't hear anything" to true
        SpeechRecognizer.ERROR_AUDIO -> "Microphone error" to true
        SpeechRecognizer.ERROR_NETWORK,
        SpeechRecognizer.ERROR_NETWORK_TIMEOUT,
        -> "Recognition needs a network connection" to true

        SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS -> "Microphone permission denied" to false
        SpeechRecognizer.ERROR_RECOGNIZER_BUSY -> "Recognizer is busy" to true
        SpeechRecognizer.ERROR_LANGUAGE_NOT_SUPPORTED,
        SpeechRecognizer.ERROR_LANGUAGE_UNAVAILABLE,
        -> "That language is not installed for offline recognition" to false

        else -> "Recognition failed" to true
    }

    private companion object {
        const val TAG = "SpeechRecognition"
    }
}
