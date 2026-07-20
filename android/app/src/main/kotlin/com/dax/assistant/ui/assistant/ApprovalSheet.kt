package com.dax.assistant.ui.assistant

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.unit.dp
import com.dax.assistant.assistant.ApprovalRequest
import com.dax.assistant.R
import com.dax.assistant.ui.design.Orbita
import com.dax.assistant.ui.design.OrbitaType

/**
 * Confirmation for a gated tool.
 *
 * This is the app's main defence against prompt injection. Everything upstream
 * of it — the user's speech, the model's reasoning, a web page a tool fetched —
 * is untrusted, and a request talked into existence by injected text produces a
 * frame indistinguishable from a legitimate one. The user is the only component
 * that can tell them apart, so this sheet exists to give them what they need to
 * do that:
 *
 *  * **Every argument in full.** Truncating the one that matters is how a
 *    destructive path gets approved. Long values scroll; nothing is elided.
 *  * **Arguments in mono, prose in sans.** They are machine facts, and the
 *    typographic split makes it obvious they were not written by a person.
 *  * **Deny is never harder to reach than approve.** Both are full-width and
 *    the same size; approve is merely tinted.
 *
 * There is no dismiss-by-tapping-outside. An ignored request is denied by the
 * backend on timeout, but a stray tap that reads as "not now" should not be the
 * same gesture as an explicit refusal.
 */
@Composable
fun ApprovalSheet(
    request: ApprovalRequest,
    onDecision: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    BoxWithConstraints(
        modifier = modifier
            .fillMaxSize()
            .background(Color.Black.copy(alpha = 0.72f)),
        contentAlignment = Alignment.BottomCenter,
    ) {
        val sheetMaxHeight = maxHeight - Orbita.spacing.x6
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(Orbita.spacing.x3)
                .heightIn(max = sheetMaxHeight)
                .clip(RoundedCornerShape(Orbita.radii.xxl))
                .background(Orbita.colors.bgElevated)
                .verticalScroll(rememberScrollState())
                .padding(Orbita.spacing.x6),
        ) {
            Text(
                text = stringResource(R.string.approval_title),
                style = OrbitaType.title1,
                color = Orbita.colors.fgPrimary,
                modifier = Modifier.semantics { heading() },
            )
            Spacer(Modifier.height(Orbita.spacing.x2))
            Text(
                text = stringResource(R.string.approval_explanation),
                style = OrbitaType.callout,
                color = Orbita.colors.fgSecondary,
            )

            Spacer(Modifier.height(Orbita.spacing.x5))

            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(Orbita.radii.lg))
                    .background(Orbita.colors.bgInset)
                    .padding(Orbita.spacing.x4),
            ) {
                Text(
                    text = request.toolName,
                    style = OrbitaType.mono,
                    color = Orbita.colors.warning,
                )
                Text(
                    text = request.serverName,
                    style = OrbitaType.monoSmall,
                    color = Orbita.colors.fgQuaternary,
                )

                if (request.arguments.isNotEmpty()) {
                    Spacer(Modifier.height(Orbita.spacing.x3))
                    Column(
                        modifier = Modifier
                            .heightIn(max = 220.dp)
                            .fillMaxWidth(),
                        verticalArrangement = Arrangement.spacedBy(Orbita.spacing.x2),
                    ) {
                        request.arguments.forEach { (key, value) ->
                            Column {
                                Text(
                                    text = key,
                                    style = OrbitaType.label,
                                    color = Orbita.colors.fgQuaternary,
                                )
                                Text(
                                    text = value,
                                    style = OrbitaType.monoSmall,
                                    color = Orbita.colors.fgPrimary,
                                )
                            }
                        }
                    }
                }
            }

            Spacer(Modifier.height(Orbita.spacing.x5))

            // Approve options come from the backend — a shell gate offers
            // "once" and "save", a plain gate offers "approve".
            request.options.filter { it != "deny" }.forEach { option ->
                DecisionButton(
                    label = approvalDecisionLabel(option),
                    background = Orbita.colors.warning,
                    foreground = Orbita.colors.fgOnAccent,
                    onClick = { onDecision(option) },
                )
                Spacer(Modifier.height(Orbita.spacing.x2))
            }

            DecisionButton(
                label = stringResource(R.string.chat_deny),
                background = Orbita.colors.bgPanel,
                foreground = Orbita.colors.fgPrimary,
                onClick = { onDecision("deny") },
            )

            Spacer(Modifier.height(Orbita.spacing.x3))
            Text(
                text = pluralStringResource(
                    R.plurals.approval_timeout,
                    request.timeoutSeconds,
                    request.timeoutSeconds,
                ),
                style = OrbitaType.footnote,
                color = Orbita.colors.fgQuaternary,
            )
        }
    }
}

@Composable
private fun approvalDecisionLabel(option: String): String = when (option) {
    "once" -> stringResource(R.string.chat_approve_once)
    "save" -> stringResource(R.string.chat_approve_save)
    else -> stringResource(R.string.chat_allow)
}

@Composable
private fun DecisionButton(
    label: String,
    background: Color,
    foreground: Color,
    onClick: () -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .heightIn(min = Orbita.sizing.controlHeight)
            .clip(RoundedCornerShape(Orbita.radii.pill))
            .background(background)
            .clickable(role = Role.Button, onClick = onClick)
            .padding(Orbita.spacing.x4),
        horizontalArrangement = Arrangement.Center,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(text = label, style = OrbitaType.title3, color = foreground)
    }
}
