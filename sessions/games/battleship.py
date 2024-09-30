from __future__ import annotations
from typing import Optional

from dataclasses import dataclass
import discord
import random


@dataclass(init=True, repr=True, slots=True)
class Cell:
    emoji: Optional[str]

    # True -> hit
    # False -> miss
    # None -> inactive
    # enemy_sate is how this cell has been interacted with an enemy hit
    # bomb_state is how this cell has been interaction with your hit

    enemy_state: Optional[bool]
    bomb_state: Optional[bool]
    button: Optional[Button] = None

    @property
    def ship(self) -> bool:
        return self.emoji is not None

    @classmethod
    def empty(cls) -> Cell:
        return cls(emoji=None, enemy_state=None, bomb_state=None)

    @property
    def display_emoji(self) -> Optional[str]:
        if self.enemy_state is None:
            return self.emoji

        if self.enemy_state:
            return "💣"
        return "🌀"


class PlayerState:
    def __init__(self, member: discord.abc.User) -> None:
        self.member: discord.abc.User = member
        self.view: Optional[BoardView] = None
        self.ready: bool = False
        self.current_player: bool = False
        empty = Cell.empty
        self.board: list[list[Cell]] = [
            [empty(), empty(), empty(), empty(), empty()],
            [empty(), empty(), empty(), empty(), empty()],
            [empty(), empty(), empty(), empty(), empty()],
            [empty(), empty(), empty(), empty(), empty()],
            [empty(), empty(), empty(), empty(), empty()],
        ]

        # self.generate_board()

    def generate_board(self) -> None:
        for size, emoji in ((4, "🚢"), (3, "⛵"), (2, "🛶")):
            dx, dy = (1, 0) if random.randint(0, 1) else (0, 1)
            positions = self.get_available_positions(dx, dy, size)

            x, y = random.choice(positions)

            for _ in range(0, size):
                self.board[x][y].emoji = emoji
                x += dx
                y += dy

    def can_place_ship(self, x: int, y: int, dx: int, dy: int, size: int) -> bool:
        bounds = range(0, 5)

        for _ in range(0, size):
            if x not in bounds or y not in bounds:
                return False

            cell = self.board[y][x]

            if cell.ship:
                return False

            x += dx
            y += dy

        return True

    def get_available_positions(
        self, dx: int, dy: int, size: int
    ) -> list[tuple[int, int]]:
        return [
            (x, y)
            for x in range(0, 5)
            for y in range(0, 5)
            if self.can_place_ship(x, y, dx, dy, size)
        ]

    def is_dead(self) -> bool:
        for y in range(5):
            for x in range(5):
                cell = self.board[y][x]

                if cell.ship and not cell.enemy_state:
                    return False
        return True

    def is_ship_shrunk(self, emoji: str) -> bool:
        for y in range(5):
            for x in range(5):
                cell = self.board[y][x]

                if cell.emoji == emoji and not cell.enemy_state:
                    return False
        return True


# Red Button (disabled) -> You hit (bomb_state: True)
# Blue Button (emabled) -> Potential hit (bomb_state: None)
# Blue button (disabled) -> Bomb missed (bomb_state: False)
# Ship emoji -> You have a ship (enemy_state: None)
# Bomb emoji -> Enemy hit that spot and missed (enemy_state: False)
# Boom emoji -> Enemy hit that spot and succeeded (enemy_state: True)


class Button(discord.ui.Button["BoardView"]):
    def __init__(self, cell: Cell, x: int, y: int) -> None:
        super().__init__(
            label="\u200b",
            style=(
                discord.ButtonStyle.red
                if cell.bomb_state
                else discord.ButtonStyle.blurple
            ),
            disabled=cell.bomb_state is not None,
            emoji=cell.display_emoji,
            row=y,
        )

        self.x: int = x
        self.y: int = y
        self.cell: Cell = cell
        cell.button = self

    def update(self) -> None:
        self.style = (
            discord.ButtonStyle.red
            if self.cell.bomb_state
            else discord.ButtonStyle.blurple
        )
        self.disabled = self.cell.bomb_state is not None
        self.emoji = self.cell.display_emoji

    async def callback(self, itx: discord.Interaction) -> None:
        assert self.view is not None, "Un error inesperado ha ocurrido"
        # assert keyword is the same as
        # if not []:
        #     raise AssertionError(<>)

        enemy = self.view.enemy
        player = self.view.player
        enemy_cell = enemy.board[self.y][self.x]

        self.cell.bomb_state = enemy_cell.ship
        enemy_cell.enemy_sate = enemy_cell.ship

        self.update()

        player.current_player = not player.current_player
        enemy.current_player = not enemy.current_player

        if enemy.is_dead():
            self.view.disable()

            await itx.response.edit_message(content="¡Ganaste!", view=self.view)

            if enemy_cell.button and enemy_cell.button.view:
                enemy_cell.button.update()

                view = enemy_cell.button.view

                await view.message.edit(content="Perdiste :(", view=view)

            await self.view.parent_message.edit(
                content=f"{player.member.mention} ha ganado esta partida, ¡felicidades!"
            )
            return

        content = f"Turno de {enemy.member.mention}"
        enemy_content = f"¡Tu ({enemy.member.mention}) turno!"

        if enemy_cell.emoji is not None and enemy.is_ship_sunk(enemy_cell.emoji):
            content = f"{content}\n\n¡Has hundido su {enemy_cell.emoji}!"
            enemy_content = f"{enemy_content}\n\nTu {enemy_cell.emoji} fue hundido :("

        await itx.response.edit_message(content=content, view=self.view)

        self.view.message = await itx.original_response()

        if enemy_cell.button and enemy_cell.button.view:
            enemy_cell.button.update()
            view = enemy_cell.button.view
            await view.message.edit(content=enemy_content, view=view)


class BoardView(discord.ui.View):
    message: discord.InteractionMessage
    parent_message: discord.Message
    children: list[Button]

    def __init__(self, player: PlayerState, enemy: PlayerState) -> None:
        super().__init__(timeout=None)

        self.player: PlayerState = player
        self.enemy: PlayerState = enemy

        for x in range(5):
            for y in range(5):
                self.add_item(Button(self.player.board[y][x], x, y))

    async def interaction_check(self, itx: discord.Interaction) -> bool:
        if not self.enemy.ready:
            await itx.response.send_message(
                "Tu enemigo no está list aún, por favor, espere a que se prepare.",
                ephemeral=True,
            )
            return False

        if not self.player.current_player:
            await itx.response.send_message("No es tu turno todavía", ephemeral=True)

    def disable(self) -> None:
        for button in self.children:
            button.disabled = True


class BoardSetupButton(discord.ui.Button["BoardSetupView"]):
    def __init__(self, x: int, y: int) -> None:
        super().__init__(label="\u200b", style=discord.ButtonStyle.blurple, row=y)

        self.x: int = x
        self.y: int = y

    async def callback(self, itx: discord.Interaction) -> None:
        assert self.view is not None, "Un error inesperado ha ocurrido"

        try:
            self.view.place_at(self.x, self.y)
        except RuntimeError as e:
            await itx.response.send_message(str(e), ephemeral=True)

        else:
            if self.view.is_done():
                await self.view.commit(itx)

            else:
                await itx.response.edit_message(view=self.view)


class BoardSetupView(discord.ui.View):
    children: list[BoardSetupButton]

    def __init__(
        self, player: PlayerState, enemy: PlayerState, parent_button: ReadyButton
    ) -> None:
        super().__init__()

        self.player: PlayerState = player
        self.enemy: PlayerState = enemy
        self.parent_button: ReadyButton = parent_button

        assert parent_button.view

        self.parent_view: Prompt = parent_button.view
        self.last_location: Optional[tuple[int, int]] = None

        # A total list of placements for the board
        # This is a tuple of (x, y, emoji).
        # The total length must be equal to 9 (4 + 3 + 2)

        self.placements: list[tuple[int, int, str]] = []
        self.taken_length: set[int] = set()

        for y in range(5):
            for x in range(5):
                self.add_item(BoardSetupButton(x, y))

    def can_place_ship(self, x: int, y: int, dx: int, dy: int, size: int) -> bool:
        bounds = range(0, 5)

        for _ in range(0, size):
            if x not in bounds or y not in bounds:
                return False

            if any(a == x and b == y for a, b, _ in self.placements):
                return False

            x += dx
            y += dy

        return True

    async def commit(self, itx: discord.Interaction) -> None:
        for x, y, emoji in self.placements:
            self.player.board[y][x].emoji = emoji

        self.player.ready = True

        board = BoardView(self.player, self.enemy)
        place = "primero" if self.player.current_player else "segundo"
        content = (
            f"¡Estás listo! Este es tu tablero, ¡Vas {place}! ¡No borres este mensaje!"
        )

        await itx.response.edit_message(content=content, view=board)

        board.message = await itx.original_response()
        board.parent_message = self.parent_view.message

        self.player.view = board
        self.parent_button.disabled = True
        self.parent_button.label = f"¡{self.player.member} está listo!"

        content = discord.utils.MISSING

        if self.parent_view.both_players_ready():
            self.parent_view.clear_items()
            self.parent_view.timeout = None
            self.parent_view.add_item(ReopenBoardButton())

            content = (
                f"Juego en progreso entre {self.player.member.mention} y {self.enemy.member.mention}...\n"
                f"{CHEATSHEET_GUIDE}\n"
                "Si accidentalmente eliminaste tu tablero, pulsa el botón de abajo para reabrirla. "
                "Ten en cuenta que esto invalida tu tabla previa."
            )

        await self.parent_view.message.edit(content=content, view=self.parent_view)

    def place_at(self, x: int, y: int):
        if self.last_location is None:
            self.last_location = (x, y)
            self.children[x + y * 5].emoji = "🚧"
        elif self.last_location == (x, y):
            self.last_location = None
            self.children[x + y * 5].emoji = None
        else:
            old_x, old_y = self.last_location
            # If both x and y are diff then we try a diagonal boat
            # This is __forbidden__

            if old_x != x and old_y != y:
                raise RuntimeError("Perdón, no puedes tener piezas diagonales")

            if old_x != x:
                size = abs(old_x - x) + 1
                dx, dy = (1, 0)
                start_x, start_y = min(old_x, x), y
            elif old_y != y:
                size = abs(old_y - y) + 1
                dx, dy = (0, 1)
                start_x, start_y = x, min(old_y, y)
            else:
                raise RuntimeError(
                    "Perdón, no pude comprender que estabas intentando hacer ahí"
                )

            boats = {4: "🚢", 3: "⛵", 2: "🛶"}

            if size not in boats:
                raise RuntimeError(
                    "Perdón, este barco es muy grande. Solo barcos de tamaños 4, 3 o 2 se permiten"
                )

            if size in self.taken_length:
                raise RuntimeError(f"Ya tienes un barco de {size} unidades de largo")

            if not self.can_place_ship(start_x, start_y, dx, dy, size):
                raise RuntimeError("Este barco será bloqueado")

            emoji = boats[size]
            for _ in range(size):
                self.placements.append((start_x, start_y, emoji))
                button = self.children[start_x + start_y * 5]
                button.emoji = emoji
                button.disabled = True

                start_x += dx
                start_y += dy

            self.taken_length.add(size)
            self.last_location = None

    def is_done(self) -> None:
        return len(self.placements) == 9


CHEATSHEET_GUIDE = (
    CHEATSHEET_GUIDE
) = """**Guide**
Red button → You hit the enemy ship successfully.
Disabled blue button → Your hit missed the enemy ship.
🌀 → The enemy's hit missed.
💥 → The enemy hit your ship.
"""


class ReopenBoardButton(discord.ui.Button["Prompt"]):
    def __init__(self) -> None:
        super().__init__(label="Reabrir Tu Tabla", style=discord.ButtonStyle.blurple)

    async def callback(self, interaction: discord.Interaction) -> None:
        assert self.view is not None
        view = self.view
        player = (
            view.first if interaction.user.id == view.first.member.id else view.second
        )
        enemy = (
            view.second if interaction.user.id == view.first.member.id else view.first
        )

        if player.view is not None:
            player.view.stop()

        board = BoardView(player, enemy)
        await interaction.response.send_message(
            "¡Esta es tu tabla!", view=board, ephemeral=True
        )
        player.view = board
        board.message = await interaction.original_response()
        board.parent_message = view.message


class ReadyButton(discord.ui.Button["Prompt"]):
    def __init__(self, player: PlayerState, enemy: PlayerState) -> None:
        super().__init__(
            label=f"Botón de {player.member.display_name}",
            style=discord.ButtonStyle.blurple,
        )
        self.player: PlayerState = player
        self.enemy: PlayerState = enemy

    async def callback(self, interaction: discord.Interaction) -> None:
        assert self.view is not None
        assert interaction.message is not None

        if interaction.user.id != self.player.member.id:
            await interaction.response.send_message(
                "Este botón de preparado no es para tí, perdón.", ephemeral=True
            )
            return

        setup = BoardSetupView(self.player, self.enemy, self)
        content = (
            "Organiza tu tabla abajo. Para poder organizarla "
            "solo pulsa 2 puntos y un barco será creado automáticamente por tí. __No puedes tener barcos diagonales__.\n\n"
            "Hay 3 barcos: 🚢, ⛵ y 🛶. Solo puedes tener 1 de cada. "
            "Son de las siguientes longitudes:\n"
            "🚢 → 4\n⛵ → 3\n🛶 → 2\n\n"
            "Puedes pulsar el mismo botón para cancelar la colocación más reciente. "
            "**No puedes mover barcos ya colocados**. "
            "¡Cuando acabes de configurar todo estarás listo para jugar!"
        )
        await interaction.response.send_message(content, view=setup, ephemeral=True)


class Prompt(discord.ui.View):
    message: discord.Message
    children: list[discord.ui.Button]

    def __init__(self, first: discord.abc.User, second: discord.abc.User):
        super().__init__(timeout=300.0)
        self.first: PlayerState = PlayerState(first)
        self.second: PlayerState = PlayerState(second)

        current_player_id = random.choice([first, second]).id
        if current_player_id == first.id:
            self.first.current_player = True
        else:
            self.second.current_player = True

        self.add_item(ReadyButton(self.first, self.second))
        self.add_item(ReadyButton(self.second, self.first))

    def disable(self) -> None:
        for button in self.children:
            button.disabled = True

    async def on_timeout(self) -> None:
        self.disable()
        await self.message.edit(
            content="La propuesta se ha cancelado automáticamente", view=self
        )

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id not in (self.first.member.id, self.second.member.id):
            await interaction.response.send_message(
                "Esta propuesta no es para tí", ephemeral=True
            )
            return False
        return True

    def both_players_ready(self) -> bool:
        return self.first.ready and self.second.ready
