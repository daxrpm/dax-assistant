package com.dax.assistant.audio

import android.content.Context
import android.media.AudioAttributes
import android.media.MediaPlayer
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import com.dax.assistant.core.log.DaxLog
import com.dax.assistant.preferences.AppPreferences
import com.dax.assistant.preferences.SpeechOutputMode
import java.io.File
import java.util.Locale
import java.util.concurrent.atomic.AtomicInteger
import kotlinx.coroutines.CompletableDeferred

/**
 * Speaks assistant replies on this Android device.
 *
 * Server mode downloads a complete authenticated WAV synthesized by the
 * configured Kokoro, Piper, or OpenAI engine. Android mode, and the server-mode
 * fallback, use the system TextToSpeech engine. WebSocket audio is never used.
 *
 * Playback uses `USAGE_ASSISTANT` rather than `USAGE_MEDIA` so the system ducks
 * music instead of fighting it, and so a reply is not mistaken for media by
 * whatever else is holding audio focus.
 */
class Speaker(
    private val context: Context,
    private val backend: BackendSpeechClient,
    private val preferences: AppPreferences,
) {

    private val ready = CompletableDeferred<Boolean>()
    private val counter = AtomicInteger(0)
    private val stopGeneration = AtomicInteger(0)
    private val playbackLock = Any()
    private var activePlayback: Playback? = null
    private var activeMedia: MediaPlayback? = null
    private var languageTag: String = "en-US"

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
        this.languageTag = languageTag
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
        val generation = stopGeneration.get()
        if (preferences.state.value.speechOutputMode == SpeechOutputMode.SERVER) {
            val serverResult = runCatching { speakFromBackend(text) }
            if (serverResult.getOrNull() == true) return true
            if (generation != stopGeneration.get()) return false
            serverResult.exceptionOrNull()?.let { DaxLog.w(TAG, "Backend speech unavailable; using Android TTS", it) }
        }
        return speakWithAndroid(text)
    }

    private suspend fun speakWithAndroid(text: String): Boolean {
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
        stopGeneration.incrementAndGet()
        backend.cancel()
        val playback = synchronized(playbackLock) {
            activePlayback.also { activePlayback = null }
        }
        runCatching { engine.stop() }
        playback?.completion?.complete(false)
        val media = synchronized(playbackLock) { activeMedia.also { activeMedia = null } }
        media?.let {
            runCatching { it.player.stop() }
            it.player.release()
            it.completion.complete(false)
        }
    }

    fun shutdown() {
        stop()
        runCatching {
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

    private suspend fun speakFromBackend(text: String): Boolean {
        val speech = backend.synthesize(text, languageTag)
        DaxLog.d(
            TAG,
            "Backend TTS engine=${speech.engine ?: "unknown"} voice=${speech.voice ?: "default"} " +
                "fingerprint=${speech.fingerprint ?: "unknown"}",
        )
        val file = File.createTempFile("dax-speech-", ".wav", context.cacheDir)
        return try {
            file.writeBytes(speech.wav)
            playWav(file)
        } finally {
            file.delete()
        }
    }

    private suspend fun playWav(file: File): Boolean {
        val completion = CompletableDeferred<Boolean>()
        val player = MediaPlayer().apply {
            setAudioAttributes(
                AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_ASSISTANT)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                    .build(),
            )
            setDataSource(file.absolutePath)
            setOnCompletionListener { finishMedia(it, true) }
            setOnErrorListener { media, _, _ ->
                finishMedia(media, false)
                true
            }
            prepare()
        }
        synchronized(playbackLock) {
            activeMedia?.let {
                runCatching { it.player.stop() }
                it.player.release()
                it.completion.complete(false)
            }
            activeMedia = MediaPlayback(player, completion)
        }
        player.start()
        return try {
            completion.await()
        } finally {
            val active = synchronized(playbackLock) {
                activeMedia?.takeIf { it.player === player }?.also { activeMedia = null }
            }
            if (active != null) {
                runCatching { player.stop() }
                player.release()
                completion.complete(false)
            }
        }
    }

    private fun finishMedia(player: MediaPlayer, success: Boolean) {
        val active = synchronized(playbackLock) {
            activeMedia?.takeIf { it.player === player }?.also { activeMedia = null }
        }
        if (active != null) {
            player.release()
            active.completion.complete(success)
        }
    }

    private data class Playback(
        val utteranceId: String,
        val completion: CompletableDeferred<Boolean>,
    )

    private data class MediaPlayback(val player: MediaPlayer, val completion: CompletableDeferred<Boolean>)

    private companion object {
        const val TAG = "Speaker"
    }
}
