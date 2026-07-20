package com.dax.assistant.audio

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import androidx.core.content.ContextCompat
import com.dax.assistant.di.IoDispatcher
import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.withContext
import kotlin.coroutines.coroutineContext

sealed interface CaptureResult {
    data object EndOfSpeech : CaptureResult
    data object DurationLimit : CaptureResult
    data object NoSpeech : CaptureResult
}

class NativeAudioCapture(
    private val context: Context,
    @IoDispatcher private val io: CoroutineDispatcher,
) {
    suspend fun capture(
        onFrame: suspend (ByteArray) -> Unit,
        onLevel: suspend (level: Float, speechDetected: Boolean) -> Unit,
    ): CaptureResult = withContext(io) {
        check(
            ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) ==
                PackageManager.PERMISSION_GRANTED,
        ) { "Microphone permission denied" }

        val minBuffer = AudioRecord.getMinBufferSize(SAMPLE_RATE, CHANNEL, ENCODING)
        check(minBuffer > 0) { "16 kHz microphone capture is unavailable" }
        val recorder = AudioRecord(
            MediaRecorder.AudioSource.VOICE_RECOGNITION,
            SAMPLE_RATE,
            CHANNEL,
            ENCODING,
            maxOf(minBuffer, MAX_FRAME_BYTES * 2),
        )
        check(recorder.state == AudioRecord.STATE_INITIALIZED) {
            recorder.release()
            "Could not initialize the microphone"
        }

        val samples = ShortArray(MAX_FRAME_BYTES / 2)
        val endpoint = SpeechEndpointDetector()
        try {
            recorder.startRecording()
            check(recorder.recordingState == AudioRecord.RECORDSTATE_RECORDING) {
                "Could not start the microphone"
            }
            while (true) {
                coroutineContext.ensureActive()
                val count = recorder.read(samples, 0, samples.size, AudioRecord.READ_BLOCKING)
                check(count > 0) { "Microphone read failed ($count)" }
                val rms = SpeechEndpointDetector.rms(samples, count)
                val decision = endpoint.accept(count, rms)
                onLevel((rms / 8_000f).coerceIn(0f, 1f), endpoint.speechDetected)
                onFrame(samples.toPcm(count))
                when (decision) {
                    EndpointDecision.END_OF_SPEECH -> return@withContext CaptureResult.EndOfSpeech
                    EndpointDecision.NO_SPEECH_TIMEOUT -> return@withContext CaptureResult.NoSpeech
                    EndpointDecision.DURATION_LIMIT -> return@withContext CaptureResult.DurationLimit
                    EndpointDecision.CONTINUE, EndpointDecision.SPEECH_STARTED -> Unit
                }
            }
            @Suppress("UNREACHABLE_CODE")
            error("Capture loop ended unexpectedly")
        } finally {
            runCatching { recorder.stop() }
            recorder.release()
        }
    }

    private fun ShortArray.toPcm(count: Int): ByteArray =
        ByteBuffer.allocate(count * 2).order(ByteOrder.LITTLE_ENDIAN).apply {
            for (index in 0 until count) putShort(this@toPcm[index])
        }.array()

    private companion object {
        const val SAMPLE_RATE = 16_000
        const val CHANNEL = AudioFormat.CHANNEL_IN_MONO
        const val ENCODING = AudioFormat.ENCODING_PCM_16BIT
        const val MAX_FRAME_BYTES = 3_200
    }
}
