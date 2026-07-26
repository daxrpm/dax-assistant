package com.dax.assistant.capabilities

import com.dax.assistant.data.protocol.CapabilityServerFrame
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class AndroidCapabilityExecutorTest {
    @Test
    fun `effectful phone action cannot bypass human approval`() = runTest {
        val context = RuntimeEnvironment.getApplication()
        val executor = AndroidCapabilityExecutor(context, NotificationHistory(context), AppVisibility())
        val request = CapabilityServerFrame.Execute(
            generation = 1,
            requestId = "request",
            toolName = "app_open",
            arguments = buildJsonObject { put("app", "Settings") },
            approved = false,
            timeoutSeconds = 10,
        )

        val result = executor.execute(request)

        assertFalse(result.success)
        assertTrue(result.error.orEmpty().contains("approval"))
    }

    @Test
    fun `permission-gated tools are absent before the user grants access`() {
        val context = RuntimeEnvironment.getApplication()
        val names = AndroidCapabilityExecutor(context, NotificationHistory(context), AppVisibility())
            .tools.map { it.name }

        assertTrue("app_open" in names)
        assertFalse("notifications_read" in names)
        assertFalse("media_control" in names)
        assertFalse("call_place" in names)
    }

    @Test
    fun `notification payload remains valid json under the backend byte limit`() {
        val entries = List(50) { index ->
            NotificationHistoryEntry(
                key = index.toString(),
                packageName = "example.package",
                app = "Example",
                title = "Título 😀".repeat(30),
                text = "á😀".repeat(1_000),
                postedAt = index.toLong(),
                ongoing = false,
            )
        }

        val payload = boundedNotificationPayload(entries)

        kotlinx.serialization.json.Json.parseToJsonElement(payload)
        assertTrue(payload.toByteArray(Charsets.UTF_8).size <= 60 * 1024)
    }
}
