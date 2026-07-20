package com.dax.assistant.audio

import android.content.Context
import android.media.AudioAttributes
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import com.dax.assistant.core.log.DaxLog
import java.util.Locale
import java.util.concurrent.atomic.AtomicInteger
import kotlinx.coroutines.CompletableDeferred

/**
 * Speaks the assistant's replies locally.
 *
 * The backend can synthesise, but it plays on the backend host — which is a
 * desktop in another room. The `/ws/voice` contract added an explicit
 * `client_text` output mode for exactly this: the server publishes the sentence
 * and the client says it. Local synthesis is also faster, works offline, and
 * keeps the reply off the network.
 *
 * Playback uses `USAGE_ASSISTANT` rather than `USAGE_MEDIA` so the system ducks
 * music instead of fighting it, and so a reply is not mistaken for media by
 * whatever else is holding audio focus.
 */
class Speaker(context: Context) {

    private val ready = CompletableDeferred<Boolean>()
    private val counter = AtomicInteger(0)
    private val playbackLock = Any()
    private var activePlayback: Playback? = null

    private val engine: TextToSpeech = TextToSpeech(context) { status ->
        val ok = status == TextToSpeech.SUCCESS
        if (!ok) DaxLog.w(TAG, "TTS engine unavailable")
        ready.complete(ok)
    }.apply {
        setAudioAttributes(
            AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_ASSISTANT)
                .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                .build(),
        )
    }

    suspend fun isReady(): Boolean = ready.await()

    fun setLanguage(languageTag: String) {
        runCatching {
            val locale = Locale.forLanguageTag(languageTag)
            val result = engine.setLanguage(locale)
            if (result == TextToSpeech.LANG_MISSING_DATA ||
                result == TextToSpeech.LANG_NOT_SUPPORTED
            ) {
                DaxLog.w(TAG, "TTS has no voice for $languageTag; using the engine default")
            }
        }
    }

    /**
     * Speaks [text] and suspends until it finishes.
     *
     * Cancelling the caller stops playback immediately, which is what makes
     * barge-in work: the user interrupting must silence the assistant now, not
     * at the end of the sentence.
     */
    suspend fun speak(text: String): Boolean {
        if (text.isBlank()) return true
        if (!isReady()) return false

        val utteranceId = "dax-${counter.incrementAndGet()}"
        val completion = CompletableDeferred<Boolean>()
        synchronized(playbackLock) {
            activePlayback?.completion?.complete(false)
            activePlayback = Playback(utteranceId, completion)
        }
        engine.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
            override fun onStart(id: String?) = Unit

            override fun onDone(id: String?) = finish(id, true)

            @Deprecated("Required override", ReplaceWith(""))
            override fun onError(id: String?) = finish(id, false)

            override fun onError(id: String?, errorCode: Int) = finish(id, false)
        })

        val queued = engine.speak(text, TextToSpeech.QUEUE_FLUSH, null, utteranceId)
        if (queued != TextToSpeech.SUCCESS) finish(utteranceId, false)
        return try {
            completion.await()
        } finally {
            stop(utteranceId)
        }
    }

    fun stop() {
        val playback = synchronized(playbackLock) {
            activePlayback.also { activePlayback = null }
        }
        runCatching { engine.stop() }
        playback?.completion?.complete(false)
    }

    fun shutdown() {
        runCatching {
            engine.stop()
            engine.shutdown()
        }
    }

    private fun finish(utteranceId: String?, success: Boolean) {
        val playback = synchronized(playbackLock) {
            activePlayback?.takeIf { it.utteranceId == utteranceId }?.also { activePlayback = null }
        }
        playback?.completion?.complete(success)
    }

    private fun stop(utteranceId: String) {
        val playback = synchronized(playbackLock) {
            activePlayback?.takeIf { it.utteranceId == utteranceId }?.also { activePlayback = null }
        }
        if (playback != null) {
            runCatching { engine.stop() }
            playback.completion.complete(false)
        }
    }

    private data class Playback(
        val utteranceId: String,
        val completion: CompletableDeferred<Boolean>,
    )

    private companion object {
        const val TAG = "Speaker"
    }
}
