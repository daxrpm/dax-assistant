package com.dax.assistant.core.log

import android.util.Log
import com.dax.assistant.BuildConfig

/**
 * Structured logging that cannot leak what the user said or what authenticates
 * them.
 *
 * Two categories are dangerous in a voice assistant and both are easy to log
 * by accident:
 *
 *  * **Voice content.** Transcripts and assistant replies are the most
 *    sensitive data this app touches. They are never logged in release, and in
 *    debug only their length is.
 *  * **Credentials.** Device secrets, bearer tokens, and pairing codes appear
 *    in request bodies and error messages, which is exactly where a lazy
 *    `Log.d(TAG, response)` puts them in logcat for any app with READ_LOGS.
 *
 * [redact] is applied to every message rather than only at known-risky call
 * sites, because the call site that leaks is by definition the one nobody
 * thought was risky.
 */
object DaxLog {

    /**
     * Patterns for values that must never reach logcat.
     *
     * Matching is deliberately broad: a false positive costs a masked log
     * line, a false negative costs a credential.
     */
    private val sensitivePatterns: List<Regex> = listOf(
        // JSON string values for any key that smells like a credential.
        Regex(
            """("(?:device_secret|token|password|secret|authorization|code)"\s*:\s*")[^"]*(")""",
            RegexOption.IGNORE_CASE,
        ),
        // Bearer tokens wherever they appear, including inside error text.
        Regex("""(Bearer\s+)[A-Za-z0-9._\-]+""", RegexOption.IGNORE_CASE),
        // Query-string credentials, e.g. the ?token= used on WebSocket URLs.
        Regex("""([?&](?:token|secret|code)=)[^&\s]*""", RegexOption.IGNORE_CASE),
    )

    private const val MASK = "***"

    fun redact(message: String): String =
        sensitivePatterns.fold(message) { acc, pattern ->
            pattern.replace(acc) { match ->
                when (match.groupValues.size) {
                    3 -> "${match.groupValues[1]}$MASK${match.groupValues[2]}"
                    else -> "${match.groupValues[1]}$MASK"
                }
            }
        }

    /**
     * Describes user speech without reproducing it.
     *
     * Call this instead of logging a transcript. In debug builds it reports
     * the length, which is enough to debug an endpointing bug; in release it
     * reports nothing at all.
     */
    fun describeSpeech(text: String?): String = when {
        text == null -> "none"
        !BuildConfig.DEBUG -> "redacted"
        else -> "${text.length} chars"
    }

    fun d(tag: String, message: String) {
        if (BuildConfig.DEBUG) Log.d(tag, redact(message))
    }

    fun i(tag: String, message: String) = Log.i(tag, redact(message))

    fun w(tag: String, message: String, error: Throwable? = null) {
        if (error == null) Log.w(tag, redact(message)) else Log.w(tag, redact(message), error)
    }

    fun e(tag: String, message: String, error: Throwable? = null) {
        if (error == null) Log.e(tag, redact(message)) else Log.e(tag, redact(message), error)
    }
}
