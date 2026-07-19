package com.dax.assistant.diagnostics

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The report decides whether the app is allowed to route a conversation
 * through the watch. Getting [CapabilityReport.watchAudioUsable] wrong in the
 * permissive direction means the user talks into a device that cannot answer.
 */
class CapabilityReportTest {

    private fun passing(): CapabilityReport = CapabilityReport()
        .with(CheckId.HFP_PROFILE, CheckStatus.PASS)
        .with(CheckId.SCO_DEVICE_PRESENT, CheckStatus.PASS)
        .with(CheckId.COMMUNICATION_DEVICE_SELECTABLE, CheckStatus.PASS)
        .with(CheckId.MICROPHONE_CAPTURE, CheckStatus.PASS)
        .with(CheckId.SPEAKER_PLAYBACK, CheckStatus.PASS)

    @Test
    fun `a fresh report has run nothing and permits nothing`() {
        val report = CapabilityReport()

        assertFalse(report.hasRun)
        assertFalse(report.watchAudioUsable)
        assertEquals(CheckId.entries.size, report.checks.size)
        assertTrue(report.checks.all { it.status == CheckStatus.NOT_RUN })
    }

    @Test
    fun `all three audio checks passing makes the route usable`() {
        assertTrue(passing().watchAudioUsable)
    }

    @Test
    fun `capture without playback is not usable`() {
        val report = passing().with(CheckId.SPEAKER_PLAYBACK, CheckStatus.FAIL)

        assertFalse(
            "a route that hears but cannot answer must not be selected",
            report.watchAudioUsable,
        )
    }

    @Test
    fun `playback without capture is not usable`() {
        val report = passing().with(CheckId.MICROPHONE_CAPTURE, CheckStatus.FAIL)

        assertFalse(report.watchAudioUsable)
    }

    @Test
    fun `selection failing makes the route unusable regardless of the rest`() {
        val report = passing().with(CheckId.COMMUNICATION_DEVICE_SELECTABLE, CheckStatus.FAIL)

        assertFalse(report.watchAudioUsable)
    }

    @Test
    fun `a skipped check never counts as a pass`() {
        val report = passing().with(CheckId.MICROPHONE_CAPTURE, CheckStatus.SKIPPED)

        assertFalse(report.watchAudioUsable)
    }

    @Test
    fun `hfp failing does not by itself block audio`() {
        // Some devices route SCO without ever reporting under the headset
        // profile. The probe reports it, but the decision rests on what
        // actually worked, not on what was advertised.
        val report = passing().with(CheckId.HFP_PROFILE, CheckStatus.FAIL)

        assertTrue(report.watchAudioUsable)
    }

    @Test
    fun `skipRemaining marks later checks but leaves earlier results alone`() {
        val report = CapabilityReport()
            .with(CheckId.HFP_PROFILE, CheckStatus.PASS, "Redmi Watch 5 Lite")
            .with(CheckId.SCO_DEVICE_PRESENT, CheckStatus.FAIL, "not present")
            .skipRemaining(CheckId.COMMUNICATION_DEVICE_SELECTABLE, "No SCO device to test")

        assertEquals(CheckStatus.PASS, report.status(CheckId.HFP_PROFILE))
        assertEquals(CheckStatus.FAIL, report.status(CheckId.SCO_DEVICE_PRESENT))
        assertEquals(
            CheckStatus.SKIPPED,
            report.status(CheckId.COMMUNICATION_DEVICE_SELECTABLE),
        )
        assertEquals(CheckStatus.SKIPPED, report.status(CheckId.MICROPHONE_CAPTURE))
        assertEquals(CheckStatus.SKIPPED, report.status(CheckId.MEDIA_BUTTON))
    }

    @Test
    fun `skipRemaining does not overwrite a check that already ran`() {
        val report = CapabilityReport()
            .with(CheckId.MICROPHONE_CAPTURE, CheckStatus.PASS, "captured")
            .skipRemaining(CheckId.HFP_PROFILE, "aborted")

        assertEquals(CheckStatus.PASS, report.status(CheckId.MICROPHONE_CAPTURE))
    }

    @Test
    fun `counts summarise the run`() {
        val report = passing().with(CheckId.MEDIA_BUTTON, CheckStatus.FAIL)

        assertEquals(5, report.passCount)
        assertEquals(1, report.failCount)
    }

    @Test
    fun `shareable text records the verdict and every check`() {
        val text = passing()
            .copy(deviceName = "Redmi Watch 5 Lite", completedAtEpochMillis = 1L)
            .with(CheckId.MEDIA_BUTTON, CheckStatus.FAIL, "no event received")
            .toShareableText()

        assertTrue(text.contains("Redmi Watch 5 Lite"))
        assertTrue(text.contains("Watch/headset audio usable: true"))
        assertTrue(text.contains("[FAIL]"))
        assertTrue(text.contains("no event received"))
        CheckId.entries.forEach { assertTrue(text.contains(it.title)) }
    }
}
