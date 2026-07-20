package com.dax.assistant.ui.setup

import java.net.URI
import java.net.URLDecoder
import java.nio.charset.StandardCharsets

data class PairingPayload(val backendUrl: String, val code: String) {
    companion object {
        fun parse(raw: String): PairingPayload? = runCatching {
            val uri = URI(raw.trim())
            if (!uri.scheme.equals("dax", ignoreCase = true) ||
                !uri.host.equals("pair", ignoreCase = true)
            ) return null
            val values = uri.rawQuery.orEmpty().split('&').mapNotNull { part ->
                val pieces = part.split('=', limit = 2)
                if (pieces.size != 2) null else decode(pieces[0]) to decode(pieces[1])
            }.toMap()
            val url = values["url"]?.trim().orEmpty()
            val code = values["code"]?.trim()?.uppercase().orEmpty()
            if (url.isBlank() || code.isBlank()) null else PairingPayload(url, code)
        }.getOrNull()

        private fun decode(value: String): String =
            URLDecoder.decode(value, StandardCharsets.UTF_8.name())
    }
}

internal fun isValidPairingCode(value: String): Boolean =
    value.trim().matches(Regex("[A-Za-z0-9]{8}"))
