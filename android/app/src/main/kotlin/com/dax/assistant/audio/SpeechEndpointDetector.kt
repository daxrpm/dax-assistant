package com.dax.assistant.audio

import kotlin.math.sqrt

enum class EndpointDecision { CONTINUE, SPEECH_STARTED, END_OF_SPEECH, NO_SPEECH_TIMEOUT, DURATION_LIMIT }

class SpeechEndpointDetector(
    private val sampleRate: Int = 16_000,
    private val speechThreshold: Int = 700,
    private val requiredSpeechMillis: Int = 100,
    private val trailingSilenceMillis: Int = 900,
    private val noSpeechTimeoutMillis: Int = 10_000,
    private val maxDurationMillis: Int = 30_000,
) {
    private var elapsedSamples = 0L
    private var voicedSamples = 0L
    private var silentSamples = 0L
    var speechDetected: Boolean = false
        private set

    fun accept(sampleCount: Int, rms: Int): EndpointDecision {
        require(sampleCount >= 0)
        elapsedSamples += sampleCount
        if (rms >= speechThreshold) {
            voicedSamples += sampleCount
            silentSamples = 0
            if (!speechDetected && millis(voicedSamples) >= requiredSpeechMillis) {
                speechDetected = true
                return EndpointDecision.SPEECH_STARTED
            }
        } else {
            voicedSamples = 0
            if (speechDetected) silentSamples += sampleCount
        }
        return when {
            millis(elapsedSamples) >= maxDurationMillis -> EndpointDecision.DURATION_LIMIT
            speechDetected && millis(silentSamples) >= trailingSilenceMillis -> EndpointDecision.END_OF_SPEECH
            !speechDetected && millis(elapsedSamples) >= noSpeechTimeoutMillis -> EndpointDecision.NO_SPEECH_TIMEOUT
            else -> EndpointDecision.CONTINUE
        }
    }

    private fun millis(samples: Long): Long = samples * 1_000L / sampleRate

    companion object {
        fun rms(samples: ShortArray, count: Int): Int {
            if (count <= 0) return 0
            var sum = 0.0
            for (index in 0 until count) {
                val value = samples[index].toDouble()
                sum += value * value
            }
            return sqrt(sum / count).toInt()
        }
    }
}
