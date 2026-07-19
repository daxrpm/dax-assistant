package com.dax.assistant.trigger

import android.content.Intent
import android.os.Bundle
import android.service.voice.VoiceInteractionService
import android.service.voice.VoiceInteractionSession
import android.service.voice.VoiceInteractionSessionService
import androidx.activity.ComponentActivity
import com.dax.assistant.core.log.DaxLog
import com.dax.assistant.service.AssistantService

/**
 * Registering as the system assistant.
 *
 * Two things come with the role, and the second one is why it matters more than
 * the assist gesture:
 *
 *  1. Long-press power / swipe-from-corner reaches [DaxVoiceInteractionSession].
 *  2. Android's foreground-service restrictions exempt the app that provides a
 *     `VoiceInteractionService` from the rule that a microphone service cannot
 *     be started from the background. Without the role, a trigger arriving
 *     while the app is not visible cannot legally open the microphone.
 *
 * The role cannot be granted programmatically — `RoleManager` has no request
 * flow for ASSISTANT — so the user selects Dax in Settings. HyperOS has been
 * reported to revert that selection after updates, which is why the app checks
 * rather than assumes it still holds.
 */
class DaxVoiceInteractionService : VoiceInteractionService() {
    override fun onReady() {
        super.onReady()
        DaxLog.i(TAG, "Voice interaction service ready")
    }

    private companion object {
        const val TAG = "DaxVIS"
    }
}

class DaxVoiceInteractionSessionService : VoiceInteractionSessionService() {
    override fun onNewSession(args: Bundle?): VoiceInteractionSession =
        DaxVoiceInteractionSession(this)
}

/**
 * The session the system starts for an assist gesture.
 *
 * It deliberately shows nothing. A full-screen overlay would be the wrong
 * answer on a phone that may be locked and in a pocket: the turn is started on
 * the service, the notification reports state, and the session closes
 * immediately so it never sits on top of whatever the user was doing.
 */
class DaxVoiceInteractionSession(
    private val service: DaxVoiceInteractionSessionService,
) : VoiceInteractionSession(service) {

    override fun onShow(args: Bundle?, showFlags: Int) {
        super.onShow(args, showFlags)
        DaxLog.i(TAG, "Assist gesture received")
        AssistantService.triggerTurn(service, source = "assist-gesture")
        hide()
    }

    private companion object {
        const val TAG = "DaxVISession"
    }
}

/**
 * Catches `android.intent.action.VOICE_COMMAND`.
 *
 * AOSP's `HeadsetSystemInterface.activateVoiceRecognition()` responds to an
 * `AT+BVRA=1` from a Bluetooth headset by starting an activity with this
 * action. It is an ordinary activity intent, so any app can register for it —
 * the assistant role is not required — and because the system starts it, the
 * app is legitimately foreground and may open the microphone.
 *
 * This is the path a headset's assistant button takes. The Redmi Watch 5 Lite
 * has no such control, but earbuds generally do.
 */
class VoiceCommandActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        DaxLog.i(TAG, "VOICE_COMMAND intent received")
        AssistantService.triggerTurn(this, source = "bluetooth-bvra")
        // Nothing to show: the turn runs on the service and the notification
        // carries the state. Finishing immediately keeps the launcher clean.
        finish()
    }

    private companion object {
        const val TAG = "VoiceCommandActivity"
    }
}

/** Entry point for `ACTION_ASSIST` when Dax is not the selected assistant. */
class AssistActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val source = if (intent?.action == Intent.ACTION_ASSIST) "action-assist" else "launcher"
        AssistantService.triggerTurn(this, source = source)
        finish()
    }
}
