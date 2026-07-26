package com.dax.assistant.data.auth

import io.mockk.every
import io.mockk.mockk
import kotlinx.coroutines.test.runTest
import mockwebserver3.MockResponse
import mockwebserver3.MockWebServer
import okhttp3.ExperimentalOkHttpApi
import okhttp3.OkHttpClient
import okio.Buffer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalOkHttpApi::class)
class CapabilityNodeAuthTest {
    private lateinit var server: MockWebServer
    private lateinit var clientCredentials: CredentialStore
    private lateinit var nodeCredentials: CapabilityNodeCredentialStore

    @Before
    fun setUp() {
        server = MockWebServer()
        server.start()
        val base = server.url("/").toString().trimEnd('/')
        clientCredentials = mockk { every { backendUrl } returns base }
        nodeCredentials = mockk(relaxed = true) {
            every { deviceId } returns "node"
            every { deviceSecret } returns "standing-secret"
            every { instanceId } returns "original-instance"
            every { enrollmentOrigin } returns base
            every { validToken() } returns CapabilityToken("cached-token", 300)
        }
    }

    @After
    fun tearDown() {
        server.close()
    }

    @Test
    fun `cached node token is not sent after backend identity changes`() = runTest {
        server.enqueue(
            MockResponse.Builder().code(200).body(
                Buffer().writeUtf8(
                    """{"status":"ok","instance_id":"replacement-instance","role":"authoritative","api_protocol":"dax","api_version":1,"liveness":true,"readiness":true}""",
                ),
            ).build(),
        )
        val auth = CapabilityNodeAuth(OkHttpClient(), clientCredentials, nodeCredentials)

        val result = auth.accessToken()

        assertTrue(result is CapabilityTokenResult.Failed)
        assertEquals(1, server.requestCount)
        assertEquals("/api/health", server.takeRequest().requestUrl?.encodedPath)
    }
}
