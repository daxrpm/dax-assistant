package com.dax.assistant.ui.conversations

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class SafeMarkdownTest {
    @Test
    fun `remote images are never retained as fetchable markdown`() {
        val parsed = parseSafeMarkdown(
            "# Answer\n**safe** ![tracking](https://example.test/pixel.png) `<b>`",
        ).text

        assertTrue(parsed.contains("Answer"))
        assertTrue(parsed.contains("tracking"))
        assertTrue(parsed.contains("<b>"))
        assertFalse(parsed.contains("https://"))
        assertFalse(parsed.contains("!["))
    }
}
