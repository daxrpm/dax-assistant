package com.dax.assistant.trigger

import android.content.Context
import android.content.Intent
import android.media.session.MediaSession
import android.media.session.PlaybackState
import android.os.SystemClock
import android.view.KeyEvent
import com.dax.assistant.core.log.DaxLog
import com.dax.assistant.service.AssistantService

/**
 * Turns a media-key press into an assistant turn.
 *
 * This is how a wearable that cannot carry audio still starts a conversation.
 * Gadgetbridge receives the watch's media command over Xiaomi's protobuf link
 * and dispatches it to Android as a `KeyEvent`, which lands on whichever
 * `MediaSession` is active. Registering one here makes Dax a valid target — no
 * Gadgetbridge fork, no patched build, and therefore no AGPL obligation, since
 * nothing of theirs is linked or modified.
 *
 * The trade-off is honest: media keys go to the *most recently active* session,
 * so while music is playing the buttons belong to the music app. That is
 * correct behaviour — hijacking play/pause from Spotify would be worse than
 * requiring a different trigger — and it is why this is one trigger among
 * several rather than the only one.
 *
 * Uses the platform `MediaSession` rather than `MediaSessionCompat`: minSdk is
 * 31, so the compat layer would add a legacy dependency for nothing.
 */
class MediaButtonTrigger(private val context: Context) {

    private var session: MediaSession? = null
    private var lastTriggerUptime = 0L

    fun start() {
        if (session != null) return
        session = MediaSession(context, TAG).apply {
            setCallback(object : MediaSession.Callback() {
                override fun onMediaButtonEvent(intent: Intent): Boolean {
                    val event = intent.getParcelableExtra(
                        Intent.EXTRA_KEY_EVENT,
                        KeyEvent::class.java,
                    ) ?: return false
                    if (event.action != KeyEvent.ACTION_DOWN) return false
                    return handle(event.keyCode)
                }

                override fun onPlay() {
                    handle(KeyEvent.KEYCODE_MEDIA_PLAY)
                }

                override fun onPause() {
                    handle(KeyEvent.KEYCODE_MEDIA_PAUSE)
                }
            })

            // A session must look playable to be handed media keys at all; an
            // inactive one is skipped by the media button router.
            setPlaybackState(
                PlaybackState.Builder()
                    .setActions(
                        PlaybackState.ACTION_PLAY or
                            PlaybackState.ACTION_PAUSE or
                            PlaybackState.ACTION_PLAY_PAUSE,
                    )
                    .setState(PlaybackState.STATE_PAUSED, 0L, 0f)
                    .build(),
            )
            isActive = true
        }
        DaxLog.i(TAG, "Media button trigger armed")
    }

    fun stop() {
        session?.run {
            isActive = false
            release()
        }
        session = null
    }

    private fun handle(keyCode: Int): Boolean {
        if (keyCode !in TRIGGER_KEYS) return false

        // Watches and headsets frequently emit a key twice for one press.
        // Debouncing here stops a single tap starting two turns, which would
        // otherwise cancel the first mid-sentence.
        val now = SystemClock.uptimeMillis()
        if (now - lastTriggerUptime < DEBOUNCE_MILLIS) return true
        lastTriggerUptime = now

        DaxLog.i(TAG, "Media key $keyCode started a turn")
        AssistantService.triggerTurn(context, source = "media-button")
        return true
    }

    private companion object {
        const val TAG = "DaxMediaButton"
        const val DEBOUNCE_MILLIS = 900L
        val TRIGGER_KEYS = setOf(
            KeyEvent.KEYCODE_MEDIA_PLAY,
            KeyEvent.KEYCODE_MEDIA_PAUSE,
            KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE,
            KeyEvent.KEYCODE_HEADSETHOOK,
        )
    }
}
