package com.dax.assistant.ui.conversations

import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.withStyle
import com.dax.assistant.ui.design.OrbitaType

/**
 * A deliberately small Markdown renderer. It never interprets HTML, opens a
 * WebView, activates links, or fetches images; unsupported syntax remains text.
 */
fun parseSafeMarkdown(source: String, codeColor: Color = Color.Unspecified): AnnotatedString {
    val withoutRemoteImages = REMOTE_IMAGE.replace(source) { match ->
        match.groupValues[1].takeIf { it.isNotBlank() } ?: "[image]"
    }
    return buildAnnotatedString {
        withoutRemoteImages.lines().forEachIndexed { lineIndex, rawLine ->
            val line = when {
                rawLine.startsWith("### ") -> rawLine.removePrefix("### ")
                rawLine.startsWith("## ") -> rawLine.removePrefix("## ")
                rawLine.startsWith("# ") -> rawLine.removePrefix("# ")
                rawLine.startsWith("- ") -> "• ${rawLine.removePrefix("- ")}"
                rawLine.startsWith("* ") -> "• ${rawLine.removePrefix("* ")}"
                else -> rawLine
            }
            val heading = rawLine.startsWith("#")
            if (heading) {
                withStyle(SpanStyle(fontWeight = FontWeight.SemiBold)) {
                    appendInlineMarkdown(line, codeColor)
                }
            } else {
                appendInlineMarkdown(line, codeColor)
            }
            if (lineIndex != withoutRemoteImages.lines().lastIndex) append('\n')
        }
    }
}

private fun AnnotatedString.Builder.appendInlineMarkdown(text: String, codeColor: Color) {
    var index = 0
    while (index < text.length) {
        when {
            text.startsWith("**", index) -> {
                val end = text.indexOf("**", index + 2)
                if (end >= 0) {
                    withStyle(SpanStyle(fontWeight = FontWeight.Bold)) {
                        append(text.substring(index + 2, end))
                    }
                    index = end + 2
                } else {
                    append("**")
                    index += 2
                }
            }
            text[index] == '`' -> {
                val end = text.indexOf('`', index + 1)
                if (end >= 0) {
                    withStyle(SpanStyle(fontFamily = FontFamily.Monospace, color = codeColor)) {
                        append(text.substring(index + 1, end))
                    }
                    index = end + 1
                } else {
                    append('`')
                    index++
                }
            }
            else -> {
                append(text[index])
                index++
            }
        }
    }
}

@Composable
fun SafeMarkdown(text: String, color: Color) {
    Text(
        text = parseSafeMarkdown(text, codeColor = color),
        style = OrbitaType.conversation,
        color = color,
    )
}

private val REMOTE_IMAGE = Regex("!\\[([^]]*)]\\(https?://[^)]+\\)", RegexOption.IGNORE_CASE)
