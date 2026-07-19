package com.dax.assistant.trigger

import android.speech.RecognitionService
import com.dax.assistant.core.log.DaxLog

/**
 * Required to appear in the digital-assistant picker.
 *
 * Android will not list an app as a candidate assistant unless it declares a
 * `RecognitionService` alongside its `VoiceInteractionService`, so this exists
 * to satisfy that contract.
 *
 * It deliberately does not implement recognition. Dax uses the platform
 * recognizer through [com.dax.assistant.audio.SpeechRecognition]; standing up a
 * second engine here would mean either wrapping the platform one in a loop or
 * shipping a model, and neither improves anything. Requests are rejected with
 * `ERROR_CLIENT` rather than left hanging, so a caller that finds this service
 * gets an immediate answer instead of a timeout.
 */
class DaxRecognitionService : RecognitionService() {

    override fun onStartListening(recognizerIntent: android.content.Intent?, listener: Callback?) {
        DaxLog.d(TAG, "Recognition requested from another app — declining")
        runCatching { listener?.error(android.speech.SpeechRecognizer.ERROR_CLIENT) }
    }

    override fun onCancel(listener: Callback?) = Unit

    override fun onStopListening(listener: Callback?) = Unit

    private companion object {
        const val TAG = "DaxRecognitionService"
    }
}
