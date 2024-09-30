from __future__ import annotations

import discord


class TicTacToeButton(discord.ui.Button["TicTacToeView"]):
    def __init__(self, x: int, y: int, custom_id: str) -> None:
        super().__init__(
            style=discord.ButtonStyle.secondary,
            label="\u200b",
            row=y,
            custom_id=custom_id,
        )

        self.x = x
        self.y = y

    async def callback(self, itx: discord.Interaction) -> None:
        assert self.view is not None

        view: "TicTacToeView" = self.view

        state = view.board[self.y][self.x]

        if state in (view.X, view.O):
            return

        if view.current_player == view.X:
            self.style = discord.ButtonStyle.danger
            self.label = "X"
            self.disabled = True
            view.board[self.y][self.x] = view.X
            view.current_player = view.O

            content = f"¡Ahora es el turno de {view.OPlayer.mention}!"
        else:
            self.style = discord.ButtonStyle.success
            self.label = "O"
            self.disabled = True
            view.board[self.y][self.x] = view.O
            view.current_player = view.X

            content = f"¡Ahora es el turno de {view.XPlayer.mention}!"

        winner = view.check_board_winner()

        if winner is not None:
            if winner == view.X:
                content = f"¡GANARON LAS **__X__**s, {view.XPlayer.mention}!"
            elif winner == view.O:
                content = f"¡GANARON LAS **__O__**s, {view.OPlayer.mention}!"
            else:
                content = "¡Es un empate!"

            for child in view.children:
                child.disabled = True

            view.stop()

        await itx.response.edit_message(content=content, view=view)


class TicTacToeView(discord.ui.View):
    children: list[TicTacToeButton]

    X = -1
    O = 1
    Tie = 2

    def __init__(self, x: discord.Member, o: discord.Member) -> None:
        super().__init__(timeout=None)

        self.current_player = self.X

        self.XPlayer = x
        self.OPlayer = o

        self.board = [
            [0, 0, 0],
            [0, 0, 0],
            [0, 0, 0],
        ]

        for x in range(3):
            for y in range(3):
                self.add_item(
                    TicTacToeButton(
                        x,
                        y,
                        custom_id=f"tictactoe::{self.XPlayer.guild.id}::{self.XPlayer.id}:{self.OPlayer.id}::{x}:{y}",
                    )
                )

    def check_board_winner(self):
        for across in self.board:
            value = sum(across)

            if value == 3:
                return self.O
            elif value == -3:
                return self.X

        for line in range(3):
            value = self.board[0][line] + self.board[1][line] + self.board[2][line]

            if value == 3:
                return self.O
            elif value == -3:
                return self.X

        diag = self.board[0][2] + self.board[1][1] + self.board[2][0]
        if diag == 3:
            return self.O
        elif diag == -3:
            return self.X

        diag = self.board[0][0] + self.board[1][1] + self.board[2][2]
        if diag == 3:
            return self.O
        elif diag == -3:
            return self.X

        if all(i != 0 for row in self.board for i in row):
            return self.Tie

        return None

    async def interaction_check(self, itx: discord.Interaction) -> bool:
        if itx.user.id not in (self.XPlayer.id, self.OPlayer.id):
            return False

        if (self.current_player == self.X) and itx.user.id == self.OPlayer.id:
            await itx.response.send_message(
                "No puedes interactuar ahora, no es tu turno", ephemeral=True
            )
            return False

        elif (self.current_player == self.O) and itx.user.id == self.XPlayer.id:
            await itx.response.send_message(
                "No puedes interactuar ahora, no es tu turno", ephemeral=True
            )
            return False

        return True
