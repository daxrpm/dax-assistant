package com.dax.assistant.core.network

import java.net.URI

/** Keeps cleartext device credentials on loopback or literal private networks. */
object BackendEndpointPolicy {
    fun normalize(value: String): String? {
        val trimmed = value.trim().trimEnd('/')
        val uri = runCatching { URI(trimmed) }.getOrNull() ?: return null
        val scheme = uri.scheme?.lowercase() ?: return null
        val host = uri.host?.removeSurrounding("[", "]")?.lowercase() ?: return null
        if (uri.userInfo != null || uri.query != null || uri.fragment != null) return null
        if (uri.path?.isNotEmpty() == true && uri.path != "/") return null
        if (scheme == "https") return trimmed
        if (scheme != "http" || !isPrivateHost(host)) return null
        return trimmed
    }

    internal fun isPrivateHost(host: String): Boolean {
        if (host == "localhost" || host == "::1") return true
        if (host.startsWith("fc") || host.startsWith("fd")) return true
        if (host.length >= 3 && host.startsWith("fe")) {
            val third = host[2].digitToIntOrNull(16)
            if (third != null && third in 8..11) return true
        }

        val octets = host.split('.').map { it.toIntOrNull() ?: return false }
        if (octets.size != 4 || octets.any { it !in 0..255 }) return false
        return octets[0] == 10 ||
            octets[0] == 127 ||
            (octets[0] == 172 && octets[1] in 16..31) ||
            (octets[0] == 192 && octets[1] == 168)
    }
}
