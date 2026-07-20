package com.dax.assistant.ui.conversations

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.animateColor
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.ArrowDownward
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.Build
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.ErrorOutline
import androidx.compose.material.icons.filled.ExpandMore
import androidx.compose.material.icons.filled.Shield
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.runtime.snapshotFlow
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.dax.assistant.R
import com.dax.assistant.data.conversations.ChatActivity
import com.dax.assistant.data.conversations.ChatApproval
import com.dax.assistant.data.conversations.ChatMessage
import com.dax.assistant.data.conversations.ConversationChatState
import com.dax.assistant.data.transport.ConnectionState
import com.dax.assistant.ui.design.Orbita
import com.dax.assistant.ui.design.OrbitaTheme
import com.dax.assistant.ui.design.OrbitaType
import com.dax.assistant.ui.design.rememberReduceMotion
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.launch

/**
 * The conversation thread, composed from the same parts as the desktop's
 * `Chat.tsx` so the two clients read as one product.
 *
 * Four rules carry over from the desktop and explain most of what follows:
 *
 *  1. A user turn is a raised bubble; an assistant turn is not. The assistant
 *     speaks in the page's own voice, identified by its mark rather than by a
 *     container, which is what keeps a long answer readable.
 *  2. Tool work is disclosure, never chrome. It collapses to one line and opens
 *     onto a railed list.
 *  3. The composer floats. Depth comes from elevation; the accent is spent on
 *     the send button, the single primary action on the screen.
 *  4. Nothing interactive is a hairline. Separation is shadow and ground.
 */
@Composable
internal fun ChatThread(
    chat: ConversationChatState?,
    title: String,
    connection: ConnectionState,
    loading: Boolean,
    showBack: Boolean,
    onBack: () -> Unit,
    onSend: (String) -> Boolean,
    onApproval: (String, String) -> Boolean,
    onApprovalExpired: (String) -> Unit,
    modifier: Modifier,
) {
    var input by rememberSaveable(chat?.sessionId) { mutableStateOf("") }
    val threadState = rememberLazyListState()
    val scope = rememberCoroutineScope()
    val threadItems = (chat?.messages?.size ?: 0) + if (chat?.thinking == true) 1 else 0
    var followsNewMessages by remember(chat?.sessionId) { mutableStateOf(true) }

    LaunchedEffect(threadState, chat?.sessionId) {
        snapshotFlow { threadState.layoutInfo }
            .map { info -> isNearConversationEnd(info.totalItemsCount, info.visibleItemsInfo.lastOrNull()?.index) }
            .distinctUntilChanged()
            .collect { followsNewMessages = it }
    }

    val newestIdentity = chat?.messages?.lastOrNull()?.let { it.id to it.content.length }
    val activityIdentity = chat?.liveActivity?.lastOrNull()
    LaunchedEffect(
        chat?.sessionId,
        newestIdentity,
        chat?.thinking,
        chat?.liveActivity?.size,
        activityIdentity,
    ) {
        if (followsNewMessages && threadItems > 0) threadState.animateScrollToItem(threadItems - 1)
    }

    Column(modifier.fillMaxSize().background(Orbita.colors.bgContent)) {
        ThreadHeader(title, showBack, onBack)

        when {
            loading -> Box(Modifier.weight(1f).fillMaxWidth(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator(color = Orbita.colors.accent)
            }

            chat == null -> Box(Modifier.weight(1f).fillMaxWidth(), contentAlignment = Alignment.Center) {
                Text(
                    stringResource(R.string.chat_choose),
                    style = OrbitaType.callout,
                    color = Orbita.colors.fgTertiary,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.padding(horizontal = Orbita.spacing.x8),
                )
            }

            else -> {
                Box(Modifier.weight(1f).fillMaxWidth()) {
                    if (chat.messages.isEmpty() && !chat.thinking) {
                        // Centred in the space it owns. Pinning the hero to the
                        // top of a scroller left the phone showing a screenful
                        // of nothing under two lines of text.
                        ThreadHero(Modifier.align(Alignment.Center))
                    } else {
                        LazyColumn(
                            state = threadState,
                            modifier = Modifier.fillMaxSize(),
                            contentPadding = PaddingValues(
                                start = Orbita.spacing.edge,
                                end = Orbita.spacing.edge,
                                top = Orbita.spacing.x5,
                                bottom = Orbita.spacing.x4,
                            ),
                            verticalArrangement = Arrangement.spacedBy(Orbita.spacing.x6),
                        ) {
                            items(chat.messages, key = { it.id }) { MessageTurn(it) }
                            if (chat.thinking) item(key = "activity") { ThinkingTurn(chat.liveActivity) }
                        }
                    }

                    if (!followsNewMessages && threadItems > 0) {
                        JumpToLatest(
                            onClick = {
                                followsNewMessages = true
                                scope.launch { threadState.animateScrollToItem(threadItems - 1) }
                            },
                            modifier = Modifier.align(Alignment.BottomCenter),
                        )
                    }
                }

                ThreadFooter(
                    input = input,
                    onInputChange = { input = it },
                    connection = connection,
                    error = chat.error,
                    onSend = { if (onSend(input)) input = "" },
                )

                chat.approval?.let { ApprovalDialog(it, onApproval, onApprovalExpired) }
            }
        }
    }
}

/**
 * Flat, on the content ground. The old header was a floating pill, which spent
 * a band of a small screen announcing itself and read as a stray card.
 */
@Composable
private fun ThreadHeader(title: String, showBack: Boolean, onBack: () -> Unit) {
    Row(
        Modifier.fillMaxWidth().height(56.dp)
            .padding(
                start = if (showBack) Orbita.spacing.x1 else Orbita.spacing.edge,
                end = Orbita.spacing.edge,
            ),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (showBack) {
            IconButton(onClick = onBack) {
                Icon(
                    Icons.AutoMirrored.Filled.ArrowBack,
                    stringResource(R.string.chat_back),
                    tint = Orbita.colors.fgSecondary,
                )
            }
        }
        Text(
            title.ifBlank { stringResource(R.string.chat_new_conversation) },
            style = OrbitaType.title3,
            color = Orbita.colors.fgPrimary,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
            modifier = Modifier.weight(1f).semantics { heading() },
        )
    }
}

@Composable
private fun ThreadHero(modifier: Modifier = Modifier) {
    Column(
        modifier.padding(horizontal = Orbita.spacing.x8),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Box(
            Modifier.size(64.dp)
                .shadow(Orbita.elevation.level2, RoundedCornerShape(Orbita.radii.xxl))
                .clip(RoundedCornerShape(Orbita.radii.xxl))
                .background(assistantBrush()),
            contentAlignment = Alignment.Center,
        ) {
            Icon(
                Icons.Filled.AutoAwesome,
                contentDescription = null,
                tint = Orbita.colors.fgOnAccent,
                modifier = Modifier.size(26.dp),
            )
        }
        Spacer(Modifier.height(Orbita.spacing.x5))
        Text(
            stringResource(R.string.chat_hero),
            style = OrbitaType.title1,
            color = Orbita.colors.fgPrimary,
            textAlign = TextAlign.Center,
        )
        Spacer(Modifier.height(Orbita.spacing.x2))
        Text(
            stringResource(R.string.chat_hero_body),
            style = OrbitaType.callout,
            color = Orbita.colors.fgSecondary,
            textAlign = TextAlign.Center,
            modifier = Modifier.widthIn(max = 300.dp),
        )
    }
}

/* ---------------- turns ---------------- */

@Composable
private fun MessageTurn(message: ChatMessage) {
    if (message.role == "user") UserTurn(message) else AssistantTurn(message)
}

/**
 * The role reaches assistive technology through the merged description rather
 * than a visible caption. Printing "Message from you" above every bubble was
 * screen-reader text leaking into the design.
 */
@Composable
private fun UserTurn(message: ChatMessage) {
    val roleLabel = stringResource(R.string.chat_role_you)
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
        Column(
            Modifier.widthIn(max = 320.dp)
                .semantics(mergeDescendants = true) {
                    contentDescription = "$roleLabel: ${message.content}"
                }
                .shadow(
                    Orbita.elevation.level1,
                    RoundedCornerShape(
                        topStart = Orbita.radii.xl,
                        topEnd = Orbita.radii.xl,
                        bottomEnd = Orbita.radii.md,
                        bottomStart = Orbita.radii.xl,
                    ),
                )
                .clip(
                    RoundedCornerShape(
                        topStart = Orbita.radii.xl,
                        topEnd = Orbita.radii.xl,
                        bottomEnd = Orbita.radii.md,
                        bottomStart = Orbita.radii.xl,
                    ),
                )
                .background(Orbita.colors.bgElevated)
                .padding(horizontal = Orbita.spacing.x4, vertical = Orbita.spacing.x3),
        ) {
            Text(
                message.content,
                style = OrbitaType.conversation,
                color = Orbita.colors.fgPrimary,
            )
            if (message.pending || message.failed) {
                Spacer(Modifier.height(Orbita.spacing.x1))
                Text(
                    stringResource(if (message.failed) R.string.chat_not_sent else R.string.chat_sending),
                    style = OrbitaType.caption,
                    color = if (message.failed) Orbita.colors.danger else Orbita.colors.fgQuaternary,
                )
            }
        }
    }
}

@Composable
private fun AssistantTurn(message: ChatMessage) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(Orbita.spacing.x3)) {
        AssistantMark()
        Column(Modifier.weight(1f)) {
            if (message.activity.isNotEmpty()) {
                ThoughtDisclosure(
                    events = message.activity,
                    elapsedSeconds = message.activity.lastOrNull { it.elapsedSeconds != null }?.elapsedSeconds,
                )
            }
            SelectionContainer { SafeMarkdown(message.content, Orbita.colors.fgPrimary) }
        }
    }
}

@Composable
private fun ThinkingTurn(events: List<ChatActivity>) {
    val latest = events.lastOrNull { it.type == "tool_call" }
    val headline = if (latest == null) {
        stringResource(R.string.status_thinking)
    } else {
        stringResource(R.string.chat_using_tool, latest.toolName.orEmpty())
    }

    // Matches the desktop's pulsing trail headline, and stops where the system
    // says animations are unwelcome.
    val reducedMotion = rememberReduceMotion()
    val transition = rememberInfiniteTransition(label = "trail")
    val pulsed by transition.animateColor(
        initialValue = Orbita.colors.fgSecondary,
        targetValue = Orbita.colors.fgPrimary,
        animationSpec = infiniteRepeatable(
            tween(durationMillis = 1_000, easing = LinearEasing),
            RepeatMode.Reverse,
        ),
        label = "trailColor",
    )

    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(Orbita.spacing.x3)) {
        AssistantMark()
        Column(Modifier.weight(1f)) {
            Text(
                headline,
                style = OrbitaType.body,
                color = if (reducedMotion) Orbita.colors.fgSecondary else pulsed,
            )
            val steps = events.filter { it.type == "tool_call" || it.type == "tool_result" }
            if (steps.isNotEmpty()) StepRail { steps.forEach { StepLine(it) } }
        }
    }
}

@Composable
private fun AssistantMark() {
    Box(
        Modifier.size(30.dp)
            .shadow(Orbita.elevation.level1, RoundedCornerShape(Orbita.radii.pill))
            .clip(RoundedCornerShape(Orbita.radii.pill))
            .background(assistantBrush()),
        contentAlignment = Alignment.Center,
    ) {
        Icon(
            Icons.Filled.AutoAwesome,
            contentDescription = stringResource(R.string.chat_role_assistant),
            tint = Orbita.colors.fgOnAccent,
            modifier = Modifier.size(15.dp),
        )
    }
}

@Composable
private fun assistantBrush(): Brush =
    Brush.linearGradient(listOf(Orbita.colors.accent, Orbita.colors.purple))

/* ---------------- tool disclosure ---------------- */

@Composable
private fun ThoughtDisclosure(events: List<ChatActivity>, elapsedSeconds: Double?) {
    var expanded by remember { mutableStateOf(false) }
    val calls = events.count { it.type == "tool_call" }
    if (calls == 0 && elapsedSeconds == null) return

    val summary = buildString {
        if (elapsedSeconds != null) {
            append(pluralSeconds(elapsedSeconds.toInt()))
        } else {
            append(stringResource(R.string.chat_reasoning))
        }
        if (calls > 0) {
            append(" · ")
            append(pluralStringResource(R.plurals.chat_tool_count, calls, calls))
        }
    }
    val expansionState = stringResource(
        if (expanded) R.string.settings_expanded else R.string.settings_collapsed,
    )

    Column {
        Row(
            Modifier.clip(RoundedCornerShape(Orbita.radii.sm))
                .clickable(role = Role.Button) { expanded = !expanded }
                .semantics { stateDescription = expansionState }
                .heightIn(min = Orbita.sizing.minTouchTarget)
                .padding(end = Orbita.spacing.x2),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Icon(
                Icons.Filled.ExpandMore,
                contentDescription = null,
                tint = Orbita.colors.fgTertiary,
                modifier = Modifier.size(16.dp).rotate(if (expanded) 0f else -90f),
            )
            Spacer(Modifier.width(Orbita.spacing.x1))
            Text(summary, style = OrbitaType.callout, color = Orbita.colors.fgTertiary)
        }
        AnimatedVisibility(expanded) {
            StepRail {
                events.filter { it.type == "tool_call" || it.type == "tool_result" }
                    .forEach { StepLine(it) }
            }
        }
    }
}

/**
 * The one line that survives from the desktop stylesheet: a rail marking the
 * extent of a nested sequence inside a flowing thread, which space alone cannot
 * express. Drawn at the near-invisible separator value.
 */
@Composable
private fun StepRail(content: @Composable ColumnScope.() -> Unit) {
    val rail = Orbita.colors.separator
    // Drawn rather than laid out: a 1dp Box sized by `IntrinsicSize.Min`
    // mismeasures while the disclosure above it is mid-animation.
    Column(
        Modifier.padding(top = Orbita.spacing.x2)
            .drawBehind {
                drawLine(
                    color = rail,
                    start = Offset(0f, 0f),
                    end = Offset(0f, size.height),
                    strokeWidth = 1.dp.toPx(),
                )
            }
            .padding(start = Orbita.spacing.x4),
        verticalArrangement = Arrangement.spacedBy(Orbita.spacing.x2),
        content = content,
    )
}

@Composable
private fun StepLine(event: ChatActivity) {
    val label = listOfNotNull(event.serverName, event.toolName).joinToString(" · ").ifBlank { event.type }
    Row(
        horizontalArrangement = Arrangement.spacedBy(Orbita.spacing.x2),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        when (event.type) {
            "tool_result" -> Icon(
                if (event.ok == false) Icons.Filled.ErrorOutline else Icons.Filled.Check,
                contentDescription = null,
                tint = if (event.ok == false) Orbita.colors.danger else Orbita.colors.success,
                modifier = Modifier.size(13.dp),
            )
            else -> Icon(
                Icons.Filled.Build,
                contentDescription = null,
                tint = Orbita.colors.fgTertiary,
                modifier = Modifier.size(13.dp),
            )
        }
        Text(
            label,
            style = OrbitaType.monoSmall,
            color = Orbita.colors.fgPrimary,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
            modifier = Modifier.weight(1f, fill = false),
        )
        if (event.type == "tool_result") {
            Text(
                stringResource(
                    if (event.ok == false) R.string.chat_step_failed else R.string.chat_step_done,
                ),
                style = OrbitaType.caption,
                color = Orbita.colors.fgTertiary,
            )
        }
    }
}

/* ---------------- composer ---------------- */

@Composable
private fun ThreadFooter(
    input: String,
    onInputChange: (String) -> Unit,
    connection: ConnectionState,
    error: String?,
    onSend: () -> Unit,
) {
    val connected = connection is ConnectionState.Connected
    val canSend = input.isNotBlank() && connected

    Column(
        Modifier.imePadding()
            .padding(horizontal = Orbita.spacing.x4, vertical = Orbita.spacing.x3)
            .fillMaxWidth()
            .widthIn(max = 760.dp),
    ) {
        // A card, not a pill. A pill on a field that grows to six lines reads as
        // a search box and wastes the corners it rounds away.
        Row(
            Modifier.fillMaxWidth()
                .shadow(Orbita.elevation.level2, RoundedCornerShape(Orbita.radii.xl))
                .clip(RoundedCornerShape(Orbita.radii.xl))
                .background(Orbita.colors.bgElevated)
                .padding(start = Orbita.spacing.x4, end = Orbita.spacing.x2, top = Orbita.spacing.x2, bottom = Orbita.spacing.x2),
            verticalAlignment = Alignment.Bottom,
        ) {
            BasicTextField(
                value = input,
                onValueChange = onInputChange,
                textStyle = OrbitaType.conversation.copy(color = Orbita.colors.fgPrimary),
                cursorBrush = SolidColor(Orbita.colors.accent),
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Send),
                keyboardActions = KeyboardActions(onSend = { if (canSend) onSend() }),
                maxLines = 6,
                modifier = Modifier.weight(1f)
                    .heightIn(min = 40.dp, max = 148.dp)
                    .padding(vertical = Orbita.spacing.x2),
                decorationBox = { innerTextField ->
                    Box(contentAlignment = Alignment.CenterStart) {
                        if (input.isEmpty()) {
                            Text(
                                stringResource(R.string.chat_message_hint),
                                style = OrbitaType.conversation,
                                color = Orbita.colors.fgTertiary,
                            )
                        }
                        innerTextField()
                    }
                },
            )
            Spacer(Modifier.width(Orbita.spacing.x2))
            SendButton(enabled = canSend, onClick = onSend)
        }

        error?.let {
            Spacer(Modifier.height(Orbita.spacing.x2))
            Text(
                it,
                style = OrbitaType.footnote,
                color = Orbita.colors.danger,
                textAlign = TextAlign.Center,
                modifier = Modifier.fillMaxWidth(),
            )
        }
        if (!connected) {
            Spacer(Modifier.height(Orbita.spacing.x2))
            Text(
                stringResource(R.string.chat_reconnecting),
                style = OrbitaType.footnote,
                color = Orbita.colors.warning,
                textAlign = TextAlign.Center,
                modifier = Modifier.fillMaxWidth(),
            )
        }
    }
}

@Composable
private fun SendButton(enabled: Boolean, onClick: () -> Unit) {
    IconButton(
        enabled = enabled,
        onClick = onClick,
        modifier = Modifier.size(40.dp)
            .clip(RoundedCornerShape(Orbita.radii.pill))
            .background(if (enabled) Orbita.colors.accent else Orbita.colors.bgActive),
    ) {
        Icon(
            Icons.AutoMirrored.Filled.Send,
            stringResource(R.string.chat_send),
            tint = if (enabled) Orbita.colors.fgOnAccent else Orbita.colors.fgQuaternary,
            modifier = Modifier.size(17.dp),
        )
    }
}

@Composable
private fun JumpToLatest(onClick: () -> Unit, modifier: Modifier = Modifier) {
    IconButton(
        onClick = onClick,
        modifier = modifier.padding(bottom = Orbita.spacing.x3).size(40.dp)
            .shadow(Orbita.elevation.level2, RoundedCornerShape(Orbita.radii.pill))
            .clip(RoundedCornerShape(Orbita.radii.pill))
            .background(Orbita.colors.bgElevated),
    ) {
        Icon(
            Icons.Filled.ArrowDownward,
            stringResource(R.string.chat_new_messages),
            tint = Orbita.colors.fgPrimary,
            modifier = Modifier.size(18.dp),
        )
    }
}

/* ---------------- approval ---------------- */

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun ApprovalDialog(
    approval: ChatApproval,
    onDecision: (String, String) -> Boolean,
    onExpired: (String) -> Unit,
) {
    val initialRemaining = (
        approval.timeoutSeconds -
            ((System.currentTimeMillis() - approval.requestedAtMillis) / 1_000L).toInt()
        ).coerceAtLeast(0)
    var remaining by remember(approval.approvalId) { mutableIntStateOf(initialRemaining) }
    LaunchedEffect(approval.approvalId) {
        while (remaining > 0) {
            delay(1_000)
            remaining--
        }
        onExpired(approval.approvalId)
    }
    AlertDialog(
        onDismissRequest = {},
        icon = { Icon(Icons.Filled.Shield, null, tint = Orbita.colors.warning) },
        title = {
            Text(stringResource(R.string.chat_approval_title), color = Orbita.colors.fgPrimary)
        },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(Orbita.spacing.x3)) {
                Text(
                    "${approval.serverName} · ${approval.toolName}",
                    style = OrbitaType.mono,
                    color = Orbita.colors.fgPrimary,
                )
                Column(
                    Modifier.fillMaxWidth().heightIn(max = 220.dp)
                        .clip(RoundedCornerShape(Orbita.radii.md))
                        .background(Orbita.colors.bgInset)
                        .verticalScroll(rememberScrollState())
                        .padding(Orbita.spacing.x3),
                    verticalArrangement = Arrangement.spacedBy(Orbita.spacing.x1),
                ) {
                    approval.arguments.forEach { (key, value) ->
                        Text("$key: $value", style = OrbitaType.monoSmall, color = Orbita.colors.fgSecondary)
                    }
                }
                LinearProgressIndicator(
                    progress = { remaining.toFloat() / approval.timeoutSeconds.coerceAtLeast(1) },
                    modifier = Modifier.fillMaxWidth(),
                    color = if (remaining <= 10) Orbita.colors.danger else Orbita.colors.warning,
                    trackColor = Orbita.colors.bgInset,
                )
                Text(
                    stringResource(R.string.chat_auto_deny, remaining),
                    style = OrbitaType.footnote,
                    color = Orbita.colors.fgSecondary,
                )
            }
        },
        confirmButton = {
            FlowRow(horizontalArrangement = Arrangement.spacedBy(Orbita.spacing.x1)) {
                approval.options.filterNot { it == "deny" }.forEach { option ->
                    TextButton(
                        onClick = { onDecision(approval.approvalId, option) },
                        modifier = Modifier.heightIn(min = Orbita.sizing.minTouchTarget),
                    ) {
                        Text(decisionLabel(option), color = Orbita.colors.accent)
                    }
                }
            }
        },
        dismissButton = {
            TextButton(
                onClick = { onDecision(approval.approvalId, "deny") },
                modifier = Modifier.heightIn(min = Orbita.sizing.minTouchTarget),
            ) {
                Text(stringResource(R.string.chat_deny), color = Orbita.colors.danger)
            }
        },
        containerColor = Orbita.colors.bgElevated,
    )
}

@Composable
private fun decisionLabel(option: String): String = when (option) {
    "once" -> stringResource(R.string.chat_approve_once)
    "save" -> stringResource(R.string.chat_approve_save)
    else -> stringResource(R.string.chat_allow)
}

/* ---------------- helpers ---------------- */

@Composable
private fun pluralSeconds(seconds: Int): String =
    pluralStringResource(R.plurals.chat_thought_for, seconds, seconds)

internal fun isNearConversationEnd(totalItems: Int, lastVisibleIndex: Int?): Boolean =
    totalItems == 0 || (lastVisibleIndex ?: -1) >= totalItems - 3

/* ---------------- previews ---------------- */

private val previewThread = ConversationChatState(
    sessionId = "preview",
    messages = listOf(
        ChatMessage(
            id = "1",
            role = "user",
            content = "¿Cuánto espacio libre le queda al disco externo?",
            timestamp = "",
        ),
        ChatMessage(
            id = "2",
            role = "assistant",
            content = "Al volumen externo le quedan **412 GB** libres de 1.8 TB, " +
                "así que estás al 77% de uso. El disco principal es el que está " +
                "ajustado: 94%.",
            timestamp = "",
            activity = listOf(
                ChatActivity(type = "tool_call", toolName = "shell_run", serverName = "dax-system"),
                ChatActivity(type = "tool_result", toolName = "shell_run", ok = true, elapsedSeconds = 3.0),
            ),
        ),
    ),
)

@Preview(name = "Thread dark", showBackground = true, widthDp = 412, heightDp = 860)
@Composable
private fun ChatThreadDarkPreview() {
    OrbitaTheme(darkTheme = true) { ChatThreadPreviewContent(previewThread) }
}

@Preview(name = "Thread light", showBackground = true, widthDp = 412, heightDp = 860)
@Composable
private fun ChatThreadLightPreview() {
    OrbitaTheme(darkTheme = false) { ChatThreadPreviewContent(previewThread) }
}

@Preview(name = "Thread empty", showBackground = true, widthDp = 412, heightDp = 860)
@Composable
private fun ChatThreadEmptyPreview() {
    OrbitaTheme(darkTheme = true) {
        ChatThreadPreviewContent(ConversationChatState(sessionId = "preview"))
    }
}

@Preview(name = "Thread thinking", showBackground = true, widthDp = 412, heightDp = 860)
@Composable
private fun ChatThreadThinkingPreview() {
    OrbitaTheme(darkTheme = true) {
        ChatThreadPreviewContent(
            previewThread.copy(
                thinking = true,
                liveActivity = listOf(
                    ChatActivity(type = "tool_call", toolName = "read_file", serverName = "dax-system"),
                ),
            ),
        )
    }
}

@Composable
private fun ChatThreadPreviewContent(chat: ConversationChatState) {
    ChatThread(
        chat = chat,
        title = "Espacio en disco",
        connection = ConnectionState.Connected,
        loading = false,
        showBack = true,
        onBack = {},
        onSend = { true },
        onApproval = { _, _ -> true },
        onApprovalExpired = {},
        modifier = Modifier.fillMaxSize(),
    )
}
