package com.dax.assistant.ui.conversations

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
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
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.ArrowDownward
import androidx.compose.material.icons.filled.ChatBubbleOutline
import androidx.compose.material.icons.filled.DeleteOutline
import androidx.compose.material.icons.filled.ExpandMore
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Shield
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.text.input.ImeAction
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.activity.compose.BackHandler
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.dax.assistant.R
import com.dax.assistant.data.conversations.ChatActivity
import com.dax.assistant.data.conversations.ChatApproval
import com.dax.assistant.data.conversations.ChatMessage
import com.dax.assistant.data.conversations.ConversationChatState
import com.dax.assistant.data.conversations.ConversationSummary
import com.dax.assistant.data.transport.ConnectionState
import com.dax.assistant.ui.design.Orbita
import com.dax.assistant.ui.design.OrbitaType
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.map
import androidx.compose.runtime.snapshotFlow

@Composable
fun ConversationsScreen(
    modifier: Modifier = Modifier,
    viewModel: ConversationsViewModel = hiltViewModel(),
    onDetailChanged: (Boolean) -> Unit = {},
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val detailVisible = state.chat != null || state.loadingChat
    LaunchedEffect(detailVisible) { onDetailChanged(detailVisible) }
    DisposableEffect(Unit) { onDispose { onDetailChanged(false) } }
    BackHandler(enabled = state.chat != null || state.loadingChat) { viewModel.closeDetail() }
    BoxWithConstraints(modifier.fillMaxSize().background(Orbita.colors.bgContent)) {
        val tablet = maxWidth >= 700.dp
        if (tablet) {
            Row(Modifier.fillMaxSize()) {
                ConversationList(
                    state,
                    viewModel::setSearch,
                    viewModel::newConversation,
                    viewModel::refresh,
                    viewModel::select,
                    viewModel::delete,
                    Modifier.width(330.dp).fillMaxHeight().background(Orbita.colors.bgPanel),
                )
                ChatDetail(
                    state.chat,
                    state.selectedConversationTitle(),
                    state.connection,
                    state.loadingChat,
                    false,
                    viewModel::closeDetail,
                    viewModel::send,
                    viewModel::resolveApproval,
                    viewModel::expireApproval,
                    Modifier.weight(1f),
                )
            }
        } else if (state.chat != null || state.loadingChat) {
            ChatDetail(
                state.chat,
                state.selectedConversationTitle(),
                state.connection,
                state.loadingChat,
                true,
                viewModel::closeDetail,
                viewModel::send,
                viewModel::resolveApproval,
                viewModel::expireApproval,
                Modifier.fillMaxSize(),
            )
        } else {
            ConversationList(
                state,
                viewModel::setSearch,
                viewModel::newConversation,
                viewModel::refresh,
                viewModel::select,
                viewModel::delete,
                Modifier.fillMaxSize(),
            )
        }
    }
}

@Composable
private fun ConversationList(
    state: ConversationsUiState,
    onSearch: (String) -> Unit,
    onNew: () -> Unit,
    onRefresh: () -> Unit,
    onSelect: (ConversationSummary) -> Unit,
    onDelete: (ConversationSummary) -> Unit,
    modifier: Modifier,
) {
    val query = state.search.trim()
    val filtered = state.conversations.filter {
        query.isEmpty() || it.title.contains(query, true) || it.preview.contains(query, true)
    }
    Column(modifier.padding(horizontal = Orbita.spacing.edge, vertical = Orbita.spacing.x5)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(
                    stringResource(R.string.conversations_title),
                    style = OrbitaType.largeTitle,
                    color = Orbita.colors.fgPrimary,
                    modifier = Modifier.semantics { heading() },
                )
                Text(
                    stringResource(R.string.chat_recent),
                    style = OrbitaType.caption,
                    color = Orbita.colors.fgTertiary,
                )
            }
            IconButton(onClick = onRefresh) {
                Icon(
                    Icons.Default.Refresh,
                    stringResource(R.string.chat_refresh),
                    tint = Orbita.colors.fgSecondary,
                )
            }
        }
        Spacer(Modifier.height(Orbita.spacing.x4))
        Column(verticalArrangement = Arrangement.spacedBy(Orbita.spacing.x2)) {
            OrbitaAction(
                label = stringResource(R.string.chat_new),
                icon = { Icon(Icons.Default.Add, null, tint = Orbita.colors.fgOnAccent) },
                onClick = onNew,
                modifier = Modifier.fillMaxWidth(),
            )
            SearchField(state.search, onSearch, Modifier.fillMaxWidth())
        }
        if (state.loadingList) LinearProgressIndicator(Modifier.fillMaxWidth())
        state.error?.let {
            Text(it, style = OrbitaType.footnote, color = Orbita.colors.danger, modifier = Modifier.padding(top = 8.dp))
        }
        LazyColumn(
            modifier = Modifier.weight(1f),
            contentPadding = PaddingValues(vertical = Orbita.spacing.x4),
            verticalArrangement = Arrangement.spacedBy(Orbita.spacing.x2),
        ) {
            if (filtered.isEmpty() && !state.loadingList) {
                item {
                    Text(
                        stringResource(if (query.isEmpty()) R.string.chat_empty else R.string.chat_no_matches),
                        color = Orbita.colors.fgTertiary,
                        style = OrbitaType.callout,
                        modifier = Modifier.padding(vertical = Orbita.spacing.x6),
                    )
                }
            }
            items(filtered, key = { it.id }) { conversation ->
                Row(
                    Modifier.fillMaxWidth()
                        .clip(RoundedCornerShape(Orbita.radii.xl))
                        .background(
                            if (state.selectedConversationId == conversation.id) {
                                Orbita.colors.bgSelected
                            } else {
                                Orbita.colors.bgElevated
                            },
                        )
                        .clickable(role = Role.Button) { onSelect(conversation) }
                        .padding(start = Orbita.spacing.x4, top = Orbita.spacing.x3, bottom = Orbita.spacing.x3),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Icon(
                        Icons.Default.ChatBubbleOutline,
                        null,
                        tint = Orbita.colors.accent,
                        modifier = Modifier.size(20.dp),
                    )
                    Column(Modifier.weight(1f).padding(horizontal = Orbita.spacing.x3)) {
                        Text(
                            conversation.title.ifBlank { stringResource(R.string.chat_new_conversation) },
                            style = OrbitaType.title3,
                            color = Orbita.colors.fgPrimary,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                        Text(
                            conversation.preview,
                            style = OrbitaType.caption,
                            color = Orbita.colors.fgTertiary,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                    }
                    IconButton(
                        enabled = state.deletingId != conversation.id,
                        onClick = { onDelete(conversation) },
                    ) {
                        Icon(
                            Icons.Default.DeleteOutline,
                            stringResource(R.string.chat_delete),
                            tint = Orbita.colors.danger,
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun ChatDetail(
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
        Row(
            Modifier.padding(horizontal = Orbita.spacing.x3, vertical = Orbita.spacing.x2)
                .fillMaxWidth()
                .shadow(Orbita.elevation.level1, RoundedCornerShape(Orbita.radii.xl))
                .clip(RoundedCornerShape(Orbita.radii.xl))
                .background(Orbita.colors.bgPanel)
                .padding(horizontal = Orbita.spacing.x2, vertical = Orbita.spacing.x1),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            if (showBack) {
                IconButton(onClick = onBack) {
                    Icon(
                        Icons.AutoMirrored.Filled.ArrowBack,
                        stringResource(R.string.chat_back),
                        tint = Orbita.colors.fgPrimary,
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
        if (loading) {
            Box(Modifier.weight(1f).fillMaxWidth(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator()
            }
        } else if (chat == null) {
            Box(Modifier.weight(1f).fillMaxWidth(), contentAlignment = Alignment.Center) {
                Text(stringResource(R.string.chat_choose), color = Orbita.colors.fgTertiary)
            }
        } else {
            Box(Modifier.weight(1f).fillMaxWidth()) {
                LazyColumn(
                    state = threadState,
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(Orbita.spacing.edge),
                    verticalArrangement = Arrangement.spacedBy(Orbita.spacing.x4),
                ) {
                if (chat.messages.isEmpty() && !chat.thinking) {
                    item {
                        Column(
                            Modifier.fillMaxWidth().padding(vertical = Orbita.spacing.x12),
                            horizontalAlignment = Alignment.CenterHorizontally,
                        ) {
                            Text(
                                stringResource(R.string.chat_hero),
                                style = OrbitaType.title2,
                                color = Orbita.colors.fgPrimary,
                            )
                            Text(
                                stringResource(R.string.chat_hero_body),
                                style = OrbitaType.callout,
                                color = Orbita.colors.fgTertiary,
                            )
                        }
                    }
                }
                    items(chat.messages, key = { it.id }) { MessageBubble(it) }
                    if (chat.thinking) item(key = "activity") { ActivityTrail(chat.liveActivity) }
                }
                if (!followsNewMessages && threadItems > 0) {
                    IconButton(
                        onClick = {
                            followsNewMessages = true
                            scope.launch {
                                threadState.animateScrollToItem(threadItems - 1)
                            }
                        },
                        modifier = Modifier.align(Alignment.BottomCenter).size(48.dp)
                            .clip(RoundedCornerShape(Orbita.radii.pill))
                            .background(Orbita.colors.accent),
                    ) {
                        Icon(Icons.Default.ArrowDownward, stringResource(R.string.chat_new_messages), tint = Orbita.colors.fgOnAccent)
                    }
                }
            }
            chat.error?.let {
                Text(
                    it,
                    style = OrbitaType.footnote,
                    color = Orbita.colors.danger,
                    modifier = Modifier.padding(horizontal = Orbita.spacing.edge),
                )
            }
            if (connection !is ConnectionState.Connected) {
                Text(
                    stringResource(R.string.chat_reconnecting),
                    style = OrbitaType.footnote,
                    color = Orbita.colors.warning,
                    modifier = Modifier.padding(horizontal = Orbita.spacing.edge, vertical = Orbita.spacing.x1),
                )
            }
            Row(
                Modifier.imePadding().padding(horizontal = Orbita.spacing.x3, vertical = Orbita.spacing.x2)
                    .fillMaxWidth()
                    .widthIn(max = 760.dp)
                    .align(Alignment.CenterHorizontally)
                    .shadow(Orbita.elevation.level2, RoundedCornerShape(Orbita.radii.pill))
                    .clip(RoundedCornerShape(Orbita.radii.pill))
                    .background(Orbita.colors.bgElevated)
                    .padding(start = Orbita.spacing.x4, end = Orbita.spacing.x1),
                verticalAlignment = Alignment.Bottom,
            ) {
                BasicTextField(
                    value = input,
                    onValueChange = { input = it },
                    textStyle = OrbitaType.body.copy(color = Orbita.colors.fgPrimary),
                    cursorBrush = SolidColor(Orbita.colors.accent),
                    keyboardOptions = KeyboardOptions(imeAction = ImeAction.Send),
                    keyboardActions = KeyboardActions(onSend = {
                        if (input.isNotBlank() && connection is ConnectionState.Connected && onSend(input)) input = ""
                    }),
                    maxLines = 6,
                    modifier = Modifier.weight(1f).heightIn(min = 52.dp, max = 132.dp),
                    decorationBox = { innerTextField ->
                        Box(Modifier.fillMaxSize(), contentAlignment = Alignment.CenterStart) {
                            if (input.isEmpty()) {
                                Text(
                                    stringResource(R.string.chat_message_hint),
                                    style = OrbitaType.body,
                                    color = Orbita.colors.fgTertiary,
                                )
                            }
                            innerTextField()
                        }
                    },
                )
                IconButton(
                    enabled = input.isNotBlank() && connection is ConnectionState.Connected,
                    onClick = {
                        if (onSend(input)) input = ""
                    },
                    modifier = Modifier.padding(vertical = Orbita.spacing.x1).size(48.dp)
                        .clip(RoundedCornerShape(Orbita.radii.pill))
                        .background(
                            if (input.isNotBlank() && connection is ConnectionState.Connected) {
                                Orbita.colors.accent
                            } else {
                                Orbita.colors.bgActive
                            },
                        ),
                ) {
                    Icon(
                        Icons.AutoMirrored.Filled.Send,
                        stringResource(R.string.chat_send),
                        tint = if (input.isNotBlank() && connection is ConnectionState.Connected) {
                            Orbita.colors.fgOnAccent
                        } else {
                            Orbita.colors.fgQuaternary
                        },
                        modifier = Modifier.size(18.dp),
                    )
                }
            }
            chat.approval?.let { ApprovalDialog(it, onApproval, onApprovalExpired) }
        }
    }
}

@Composable
private fun MessageBubble(message: ChatMessage) {
    val user = message.role == "user"
    val roleLabel = stringResource(if (user) R.string.chat_role_you else R.string.chat_role_assistant)
    Row(
        Modifier.fillMaxWidth().semantics(mergeDescendants = true) {},
        horizontalArrangement = if (user) Arrangement.End else Arrangement.Start,
    ) {
        Column(
            Modifier.fillMaxWidth(if (user) 0.84f else 0.94f)
                .then(
                    if (user) {
                        Modifier.clip(RoundedCornerShape(Orbita.radii.xl))
                            .background(Orbita.colors.bgSelected)
                    } else {
                        Modifier
                    },
                )
                .padding(horizontal = Orbita.spacing.x4, vertical = Orbita.spacing.x3),
        ) {
            Text(roleLabel, style = OrbitaType.caption, color = Orbita.colors.fgQuaternary)
            SelectionContainer { SafeMarkdown(message.content, Orbita.colors.fgPrimary) }
            if (message.pending || message.failed) {
                Text(
                    stringResource(if (message.failed) R.string.chat_not_sent else R.string.chat_sending),
                    style = OrbitaType.caption,
                    color = if (message.failed) Orbita.colors.danger else Orbita.colors.fgQuaternary,
                )
            }
            if (!user && message.activity.isNotEmpty()) ActivityDisclosure(message.activity)
        }
    }
}

@Composable
private fun ActivityTrail(events: List<ChatActivity>) {
    val latest = events.lastOrNull { it.type == "tool_call" }
    Column(
        Modifier.fillMaxWidth(0.94f).clip(RoundedCornerShape(Orbita.radii.xl))
            .background(Orbita.colors.bgPanel).padding(Orbita.spacing.x4),
    ) {
        Text(
            if (latest == null) stringResource(R.string.status_thinking)
            else stringResource(R.string.chat_using_tool, latest.toolName.orEmpty()),
            style = OrbitaType.callout,
            color = Orbita.colors.accent,
        )
        if (events.isNotEmpty()) ActivityDisclosure(events, initiallyExpanded = true)
    }
}

@Composable
private fun ActivityDisclosure(events: List<ChatActivity>, initiallyExpanded: Boolean = false) {
    var expanded by remember { mutableStateOf(initiallyExpanded) }
    val activityLabel = stringResource(R.string.chat_activity)
    val expansionState = stringResource(
        if (expanded) R.string.settings_expanded else R.string.settings_collapsed,
    )
    Row(
        Modifier.fillMaxWidth().clickable(role = Role.Button) { expanded = !expanded }
            .semantics {
                contentDescription = activityLabel
                stateDescription = expansionState
            }
            .heightIn(min = 48.dp).padding(top = Orbita.spacing.x2),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(Icons.Default.ExpandMore, null, tint = Orbita.colors.fgTertiary, modifier = Modifier.size(18.dp))
        Text(stringResource(R.string.chat_activity), style = OrbitaType.caption, color = Orbita.colors.fgTertiary)
    }
    if (expanded) {
        Column(verticalArrangement = Arrangement.spacedBy(Orbita.spacing.x2)) {
            events.filter { it.type == "tool_call" || it.type == "tool_result" }.forEach { event ->
                Column(Modifier.fillMaxWidth().background(Orbita.colors.bgInset, RoundedCornerShape(Orbita.radii.md)).padding(8.dp)) {
                    Text(
                        listOfNotNull(event.serverName, event.toolName).joinToString(" · ").ifBlank { event.type },
                        style = OrbitaType.monoSmall,
                        color = if (event.ok == false) Orbita.colors.danger else Orbita.colors.fgSecondary,
                    )
                    event.arguments.forEach { (key, value) ->
                        Text("$key: $value", style = OrbitaType.monoSmall, color = Orbita.colors.fgQuaternary)
                    }
                    event.preview?.let { Text(it, style = OrbitaType.monoSmall, color = Orbita.colors.fgTertiary) }
                }
            }
        }
    }
}

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
        icon = { Icon(Icons.Default.Shield, null, tint = Orbita.colors.warning) },
        title = {
            Text(
                stringResource(R.string.chat_approval_title),
                color = Orbita.colors.fgPrimary,
            )
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
                        .background(Orbita.colors.bgInset, RoundedCornerShape(Orbita.radii.md))
                        .verticalScroll(androidx.compose.foundation.rememberScrollState())
                        .padding(Orbita.spacing.x3),
                ) {
                    approval.arguments.forEach { (key, value) ->
                        Text("$key: $value", style = OrbitaType.monoSmall, color = Orbita.colors.fgSecondary)
                    }
                }
                LinearProgressIndicator(
                    progress = { remaining.toFloat() / approval.timeoutSeconds.coerceAtLeast(1) },
                    modifier = Modifier.fillMaxWidth(),
                    color = if (remaining <= 10) Orbita.colors.danger else Orbita.colors.warning,
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

internal fun isNearConversationEnd(totalItems: Int, lastVisibleIndex: Int?): Boolean =
    totalItems == 0 || (lastVisibleIndex ?: -1) >= totalItems - 3

private fun ConversationsUiState.selectedConversationTitle(): String =
    conversations.firstOrNull { it.id == selectedConversationId }?.title.orEmpty()

@Composable
private fun OrbitaAction(
    label: String,
    icon: @Composable () -> Unit,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Row(
        modifier.heightIn(min = Orbita.sizing.minTouchTarget)
            .clip(RoundedCornerShape(Orbita.radii.pill))
            .background(Orbita.colors.accent)
            .clickable(role = Role.Button, onClick = onClick)
            .padding(horizontal = Orbita.spacing.x4),
        horizontalArrangement = Arrangement.Center,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        icon()
        Spacer(Modifier.width(Orbita.spacing.x2))
        Text(label, style = OrbitaType.callout, color = Orbita.colors.fgOnAccent)
    }
}

@Composable
private fun SearchField(value: String, onValueChange: (String) -> Unit, modifier: Modifier = Modifier) {
    BasicTextField(
        value = value,
        onValueChange = onValueChange,
        singleLine = true,
        textStyle = OrbitaType.callout.copy(color = Orbita.colors.fgPrimary),
        cursorBrush = SolidColor(Orbita.colors.accent),
        modifier = modifier.heightIn(min = Orbita.sizing.minTouchTarget)
            .clip(RoundedCornerShape(Orbita.radii.pill))
            .background(Orbita.colors.bgInset)
            .padding(horizontal = Orbita.spacing.x3),
        decorationBox = { innerTextField ->
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(
                    Icons.Default.Search,
                    contentDescription = null,
                    tint = Orbita.colors.fgTertiary,
                    modifier = Modifier.size(18.dp),
                )
                Spacer(Modifier.width(Orbita.spacing.x2))
                Box(Modifier.weight(1f)) {
                    if (value.isEmpty()) {
                        Text(
                            stringResource(R.string.chat_search),
                            style = OrbitaType.callout,
                            color = Orbita.colors.fgTertiary,
                            maxLines = 1,
                        )
                    }
                    innerTextField()
                }
            }
        },
    )
}

@Composable
private fun decisionLabel(option: String): String = when (option) {
    "once" -> stringResource(R.string.chat_approve_once)
    "save" -> stringResource(R.string.chat_approve_save)
    else -> stringResource(R.string.chat_allow)
}
