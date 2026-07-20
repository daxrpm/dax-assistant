package com.dax.assistant.ui.conversations

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import com.dax.assistant.R
import com.dax.assistant.assistant.Turn
import com.dax.assistant.ui.design.Orbita
import com.dax.assistant.ui.design.OrbitaType

@Composable
fun ConversationsScreen(history: List<Turn>, modifier: Modifier = Modifier) {
    Column(modifier.fillMaxSize().background(Orbita.colors.bgWindow)) {
        Column(Modifier.padding(horizontal = Orbita.spacing.edge, vertical = Orbita.spacing.x6)) {
            Text(stringResource(R.string.conversations_title), style = OrbitaType.largeTitle)
            Spacer(Modifier.height(Orbita.spacing.x2))
            Text(
                stringResource(R.string.conversations_subtitle),
                style = OrbitaType.callout,
                color = Orbita.colors.fgTertiary,
            )
        }
        if (history.isEmpty()) {
            Text(
                stringResource(R.string.conversations_empty),
                style = OrbitaType.title2,
                color = Orbita.colors.fgSecondary,
                modifier = Modifier.padding(Orbita.spacing.edge),
            )
        } else {
            LazyColumn(
                contentPadding = PaddingValues(horizontal = Orbita.spacing.edge, vertical = Orbita.spacing.x3),
                verticalArrangement = Arrangement.spacedBy(Orbita.spacing.x3),
            ) {
                items(history.reversed(), key = { it.id }) { turn ->
                    Column(
                        Modifier.fillMaxWidth()
                            .background(Orbita.colors.bgPanel, RoundedCornerShape(Orbita.radii.xl))
                            .padding(Orbita.spacing.x5),
                    ) {
                        Text(turn.userText, style = OrbitaType.callout, color = Orbita.colors.fgTertiary)
                        Spacer(Modifier.height(Orbita.spacing.x2))
                        Text(turn.assistantText, style = OrbitaType.conversation)
                    }
                }
            }
        }
    }
}
