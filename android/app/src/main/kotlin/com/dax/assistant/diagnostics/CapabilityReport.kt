package com.dax.assistant.diagnostics

/**
 * The outcome of one capability check.
 *
 * [SKIPPED] is not a soft failure — it means a prerequisite check already
 * answered no, so running this one would report a misleading result. A probe
 * that cannot see an SCO device has not "failed to record from the watch"; it
 * never had a watch to record from.
 */
enum class CheckStatus { PASS, FAIL, SKIPPED, NOT_RUN }

/**
 * One line of the report.
 *
 * [detail] carries the observed evidence — a device name, a sample rate, an
 * exception message. It is what makes a FAIL actionable instead of just
 * discouraging, and it is what gets pasted into a bug report.
 */
data class CapabilityCheck(
    val id: CheckId,
    val title: String,
    val status: CheckStatus = CheckStatus.NOT_RUN,
    val detail: String = "",
)

/**
 * The seven questions that decide whether watch audio is usable at all.
 *
 * Order matters: each check is a prerequisite for the ones after it, so the
 * first FAIL explains every SKIPPED below it.
 */
enum class CheckId(val title: String) {
    HFP_PROFILE("Registered under the HFP/headset profile"),
    SCO_DEVICE_PRESENT("Exposed to Android as a SCO communication device"),
    COMMUNICATION_DEVICE_SELECTABLE("Selectable outside a phone call"),

    /**
     * Opening the link turned out to be the easy part.
     *
     * startVoiceRecognition() promotes the watch and SCO comes up with mSBC,
     * but the watch has no voice-recognition session to run, so its firmware
     * ends the session and the stack tears the link down roughly a second
     * later. A route that survives one second is useless for conversation, so
     * this measures how long it is actually held with a live capture stream
     * anchoring it.
     */
    ROUTE_STABILITY("Route stays open long enough to talk"),
    MICROPHONE_CAPTURE("Microphone captures audio"),
    SPEAKER_PLAYBACK("Speech plays through its speaker"),
    AUDIO_FORMAT("Negotiated sample rate and encoding"),
    MEDIA_BUTTON("Media button reaches the app"),
}

/**
 * A full probe result.
 *
 * The report is the input to runtime feature detection: [watchAudioUsable] is
 * the single question the rest of the app asks. Everything else in here exists
 * so a human can understand *why* the answer is what it is.
 */
data class CapabilityReport(
    val checks: List<CapabilityCheck> = CheckId.entries.map { CapabilityCheck(it, it.title) },
    val deviceName: String = "",
    val completedAtEpochMillis: Long = 0L,
) {
    fun status(id: CheckId): CheckStatus =
        checks.firstOrNull { it.id == id }?.status ?: CheckStatus.NOT_RUN

    /**
     * Whether the app may route a conversation through the Bluetooth device.
     *
     * Deliberately strict: capture *and* playback *and* selection must all
     * have passed. A route that records but cannot answer is worse than no
     * route, because the user talks into it and hears nothing back.
     */
    val watchAudioUsable: Boolean
        get() = status(CheckId.COMMUNICATION_DEVICE_SELECTABLE) == CheckStatus.PASS &&
            status(CheckId.ROUTE_STABILITY) == CheckStatus.PASS &&
            status(CheckId.MICROPHONE_CAPTURE) == CheckStatus.PASS &&
            status(CheckId.SPEAKER_PLAYBACK) == CheckStatus.PASS

    val hasRun: Boolean
        get() = completedAtEpochMillis > 0L

    val passCount: Int
        get() = checks.count { it.status == CheckStatus.PASS }

    val failCount: Int
        get() = checks.count { it.status == CheckStatus.FAIL }

    fun with(id: CheckId, status: CheckStatus, detail: String = ""): CapabilityReport = copy(
        checks = checks.map {
            if (it.id == id) it.copy(status = status, detail = detail) else it
        },
    )

    /**
     * Marks every not-yet-run check from [from] onward as skipped, so the
     * report never shows a bare FAIL for something that was never attempted.
     */
    fun skipRemaining(from: CheckId, reason: String): CapabilityReport {
        val startIndex = CheckId.entries.indexOf(from)
        return copy(
            checks = checks.map { check ->
                val index = CheckId.entries.indexOf(check.id)
                if (index >= startIndex && check.status == CheckStatus.NOT_RUN) {
                    check.copy(status = CheckStatus.SKIPPED, detail = reason)
                } else {
                    check
                }
            },
        )
    }

    /** A plain-text rendering suitable for sharing or pasting into an issue. */
    fun toShareableText(): String = buildString {
        appendLine("Dax audio capability report")
        if (deviceName.isNotBlank()) appendLine("Device: $deviceName")
        appendLine("Watch/headset audio usable: $watchAudioUsable")
        appendLine()
        checks.forEach { check ->
            append(
                when (check.status) {
                    CheckStatus.PASS -> "[PASS] "
                    CheckStatus.FAIL -> "[FAIL] "
                    CheckStatus.SKIPPED -> "[SKIP] "
                    CheckStatus.NOT_RUN -> "[ -- ] "
                },
            )
            append(check.title)
            if (check.detail.isNotBlank()) {
                append(" — ")
                append(check.detail)
            }
            appendLine()
        }
    }
}
