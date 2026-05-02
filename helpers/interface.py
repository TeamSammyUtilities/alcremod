import discord
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Page:
    title: Optional[str] = None
    description: Optional[str | list] = None
    color: Optional[int | str] = None
    author: Optional[dict] = None
    footer: Optional[dict] = None
    thumbnail: Optional[str] = None
    image: Optional[str] = None
    fields: list[dict] = field(default_factory=list)


class Embed:
    def __init__(self, pages: list[Page]):
        self.pages = pages

    def build(self, index: int) -> discord.Embed:
        page = self.pages[index]
        
        if isinstance(page.description, list):
            description = "\n".join(str(item) for item in page.description)
        else:
            description = page.description
            
        embed = discord.Embed(
            title=page.title,
            description=description,
            color=self._parse_color(page.color)
        )

        if page.author:
            embed.set_author(**page.author)

        if page.footer:
            embed.set_footer(**page.footer)
        elif len(self.pages) != 1:
            embed.set_footer(text=f"Page {index + 1}/{len(self.pages)}")

        if page.thumbnail:
            embed.set_thumbnail(url=page.thumbnail)

        if page.image:
            embed.set_image(url=page.image)

        for field in page.fields:
            embed.add_field(
                name=field.get("name"),
                value=field.get("value"),
                inline=field.get("inline", False)
            )

        return embed

    def _parse_color(self, color):
        if isinstance(color, int):
            return discord.Color(color)

        if isinstance(color, str):
            return discord.Color(int(color.lstrip("#"), 16))

        return discord.Color.blurple()


class Paginator(discord.ui.View):
    def __init__(self, pages: list[Page], timeout: int = 60):
        super().__init__(timeout=timeout)

        self.embed = Embed(pages)
        self.index = 0
        self.total = len(pages)

        if self.total <= 1:
            self.previous.disabled = True
            self.next.disabled = True

    def get_embed(self):
        return self.embed.build(self.index)

    @discord.ui.button(label="<", style=discord.ButtonStyle.primary)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index = (self.index - 1) % self.total
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @discord.ui.button(label=">", style=discord.ButtonStyle.primary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index = (self.index + 1) % self.total
        await interaction.response.edit_message(embed=self.get_embed(), view=self)