package com.dax.assistant.ui.conversations

import android.text.format.DateUtils
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.ChatBubbleOutline
import androidx.compose.material.icons.filled.DeleteOutline
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.dax.assistant.R
import com.dax.assistant.data.conversations.ConversationSummary
import com.dax.assistant.ui.design.Orbita
import com.dax.assistant.ui.design.OrbitaType
import java.time.Instant

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
    BackHandler(enabled = detailVisible) { viewModel.closeDetail() }

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
                ChatThread(
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
        } else if (detailVisible) {
            ChatThread(
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
                    Icons.Filled.Refresh,
                    stringResource(R.string.chat_refresh),
                    tint = Orbita.colors.fgSecondary,
                )
            }
        }

        Spacer(Modifier.height(Orbita.spacing.x4))
        Column(verticalArrangement = Arrangement.spacedBy(Orbita.spacing.x2)) {
            NewConversationButton(onNew)
            SearchField(state.search, onSearch, Modifier.fillMaxWidth())
        }
        if (state.loadingList) {
            Spacer(Modifier.height(Orbita.spacing.x2))
            LinearProgressIndicator(
                modifier = Modifier.fillMaxWidth(),
                color = Orbita.colors.accent,
                trackColor = Orbita.colors.bgInset,
            )
        }
        state.error?.let {
            Text(
                it,
                style = OrbitaType.footnote,
                color = Orbita.colors.danger,
                modifier = Modifier.padding(top = Orbita.spacing.x2),
            )
        }

        LazyColumn(
            modifier = Modifier.weight(1f),
            contentPadding = PaddingValues(vertical = Orbita.spacing.x4),
            verticalArrangement = Arrangement.spacedBy(Orbita.spacing.x2),
        ) {
            if (filtered.isEmpty() && !state.loadingList) {
                item {
                    Text(
                        stringResource(
                            if (query.isEmpty()) R.string.chat_empty else R.string.chat_no_matches,
                        ),
                        style = OrbitaType.callout,
                        color = Orbita.colors.fgTertiary,
                        textAlign = TextAlign.Center,
                        modifier = Modifier.fillMaxWidth().padding(vertical = Orbita.spacing.x10),
                    )
                }
            }
            items(filtered, key = { it.id }) { conversation ->
                ConversationRow(
                    conversation = conversation,
                    selected = state.selectedConversationId == conversation.id,
                    deleting = state.deletingId == conversation.id,
                    onSelect = { onSelect(conversation) },
                    onDelete = { onDelete(conversation) },
                )
            }
        }
    }
}

@Composable
private fun ConversationRow(
    conversation: ConversationSummary,
    selected: Boolean,
    deleting: Boolean,
    onSelect: () -> Unit,
    onDelete: () -> Unit,
) {
    val fallbackTitle = stringResource(R.string.chat_new_conversation)
    Row(
        Modifier.fillMaxWidth()
            .shadow(Orbita.elevation.level1, RoundedCornerShape(Orbita.radii.xl))
            .clip(RoundedCornerShape(Orbita.radii.xl))
            .background(if (selected) Orbita.colors.bgSelected else Orbita.colors.bgElevated)
            .clickable(role = Role.Button, onClick = onSelect)
            .padding(start = Orbita.spacing.x4, top = Orbita.spacing.x3, bottom = Orbita.spacing.x3),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(
            Icons.Filled.ChatBubbleOutline,
            contentDescription = null,
            tint = if (selected) Orbita.colors.accent else Orbita.colors.fgTertiary,
            modifier = Modifier.size(18.dp),
        )
        Column(Modifier.weight(1f).padding(horizontal = Orbita.spacing.x3)) {
            Text(
                conversation.title.ifBlank { fallbackTitle },
                style = OrbitaType.title3,
                color = Orbita.colors.fgPrimary,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Spacer(Modifier.height(2.dp))
            Row(
                horizontalArrangement = Arrangement.spacedBy(Orbita.spacing.x2),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    conversation.preview,
                    style = OrbitaType.caption,
                    color = Orbita.colors.fgTertiary,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.weight(1f, fill = false),
                )
                relativeTime(conversation.updatedAt)?.let {
                    Text(it, style = OrbitaType.caption, color = Orbita.colors.fgQuaternary, maxLines = 1)
                }
            }
        }
        IconButton(enabled = !deleting, onClick = onDelete) {
            Icon(
                Icons.Filled.DeleteOutline,
                stringResource(R.string.chat_delete),
                tint = if (deleting) Orbita.colors.fgQuaternary else Orbita.colors.fgTertiary,
                modifier = Modifier.size(18.dp),
            )
        }
    }
}

@Composable
private fun NewConversationButton(onClick: () -> Unit) {
    Row(
        Modifier.fillMaxWidth().heightIn(min = Orbita.sizing.minTouchTarget)
            .shadow(Orbita.elevation.level1, RoundedCornerShape(Orbita.radii.pill))
            .clip(RoundedCornerShape(Orbita.radii.pill))
            .background(Orbita.colors.accent)
            .clickable(role = Role.Button, onClick = onClick)
            .padding(horizontal = Orbita.spacing.x4),
        horizontalArrangement = Arrangement.Center,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(
            Icons.Filled.Add,
            contentDescription = null,
            tint = Orbita.colors.fgOnAccent,
            modifier = Modifier.size(18.dp),
        )
        Spacer(Modifier.width(Orbita.spacing.x2))
        Text(
            stringResource(R.string.chat_new),
            style = OrbitaType.title3,
            color = Orbita.colors.fgOnAccent,
        )
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
            .padding(horizontal = Orbita.spacing.x4),
        decorationBox = { innerTextField ->
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(
                    Icons.Filled.Search,
                    contentDescription = null,
                    tint = Orbita.colors.fgTertiary,
                    modifier = Modifier.size(17.dp),
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

/** Localised "2 hours ago"; absent rather than wrong when the stamp will not parse. */
private fun relativeTime(iso: String): String? = runCatching {
    DateUtils.getRelativeTimeSpanString(
        Instant.parse(iso).toEpochMilli(),
        System.currentTimeMillis(),
        DateUtils.MINUTE_IN_MILLIS,
    ).toString()
}.getOrNull()

private fun ConversationsUiState.selectedConversationTitle(): String =
    conversations.firstOrNull { it.id == selectedConversationId }?.title.orEmpty()
