package com.dax.assistant.core.network

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class BackendEndpointPolicyTest {
    @Test
    fun `capability nodes require tls away from loopback`() {
        assertTrue(BackendEndpointPolicy.allowsCapabilityNode("https://dax.example"))
        assertTrue(BackendEndpointPolicy.allowsCapabilityNode("http://127.0.0.1:8420"))
        assertFalse(BackendEndpointPolicy.allowsCapabilityNode("http://192.168.1.20:8420"))
        assertFalse(BackendEndpointPolicy.allowsCapabilityNode("http://100.64.1.2:8420"))
    }
    @Test
    fun `allows https and private cleartext backends`() {
        assertEquals("https://dax.example", BackendEndpointPolicy.normalize(" https://dax.example/ "))
        assertEquals("http://192.168.100.104:8420", BackendEndpointPolicy.normalize("http://192.168.100.104:8420"))
        assertEquals("http://10.0.2.2:8420", BackendEndpointPolicy.normalize("http://10.0.2.2:8420"))
        assertEquals("http://172.16.0.1:8420", BackendEndpointPolicy.normalize("http://172.16.0.1:8420"))
        assertEquals("http://localhost:8420", BackendEndpointPolicy.normalize("http://localhost:8420"))
        assertEquals("http://[::1]:8420", BackendEndpointPolicy.normalize("http://[::1]:8420"))
    }

    @Test
    fun `allows the overlay range Tailscale assigns from`() {
        assertEquals("http://100.64.0.2:8420", BackendEndpointPolicy.normalize("http://100.64.0.2:8420"))
        assertTrue(BackendEndpointPolicy.isPrivateHost("100.64.0.0"))
        assertTrue(BackendEndpointPolicy.isPrivateHost("100.127.255.255"))
        // 100.63 and 100.128 bracket RFC 6598.
        assertFalse(BackendEndpointPolicy.isPrivateHost("100.63.255.255"))
        assertFalse(BackendEndpointPolicy.isPrivateHost("100.128.0.0"))
    }

    @Test
    fun `rejects public cleartext and hostname confusion`() {
        assertNull(BackendEndpointPolicy.normalize("http://example.com:8420"))
        assertNull(BackendEndpointPolicy.normalize("http://localhost.attacker.example:8420"))
        assertNull(BackendEndpointPolicy.normalize("http://192.168.attacker.example:8420"))
        assertNull(BackendEndpointPolicy.normalize("http://172.32.0.1:8420"))
        assertNull(BackendEndpointPolicy.normalize("ftp://192.168.1.2/file"))
    }

    @Test
    fun `rejects credentials paths queries and malformed addresses`() {
        assertNull(BackendEndpointPolicy.normalize("http://user:pass@192.168.1.2:8420"))
        assertNull(BackendEndpointPolicy.normalize("http://192.168.1.2:8420/api"))
        assertNull(BackendEndpointPolicy.normalize("http://192.168.1.2:8420?q=1"))
        assertNull(BackendEndpointPolicy.normalize("http://192.168.1.999:8420"))
        assertNull(BackendEndpointPolicy.normalize("not a url"))
    }

    @Test
    fun `recognizes all RFC1918 ranges`() {
        assertTrue(BackendEndpointPolicy.isPrivateHost("10.255.255.255"))
        assertTrue(BackendEndpointPolicy.isPrivateHost("172.31.255.255"))
        assertTrue(BackendEndpointPolicy.isPrivateHost("192.168.0.1"))
    }

    @Test
    fun `only accepts fc fd and fe prefixes on real IPv6 literals`() {
        assertTrue(BackendEndpointPolicy.isPrivateHost("fc00::1"))
        assertTrue(BackendEndpointPolicy.isPrivateHost("fd12:3456::1"))
        assertTrue(BackendEndpointPolicy.isPrivateHost("fe80::1"))
        assertFalse(BackendEndpointPolicy.isPrivateHost("fc-attacker.example"))
        assertFalse(BackendEndpointPolicy.isPrivateHost("fd.example"))
        assertFalse(BackendEndpointPolicy.isPrivateHost("fe80.example"))
        assertFalse(BackendEndpointPolicy.isPrivateHost("fe-not-ipv6"))
        assertNull(BackendEndpointPolicy.normalize("http://fc-attacker.example:8420"))
        assertNull(BackendEndpointPolicy.normalize("http://fe80.example:8420"))
    }
}
