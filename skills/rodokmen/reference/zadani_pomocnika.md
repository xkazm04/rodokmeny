# Zadání pomocníka (subagenta) – vzor a pravidla

Pomocníci ztrácejí a vymýšlejí obsah snímků (přiznali to jen díky kontrolní tabulce) a jeden zacyklený pomocník umí
spálit 5hodinový limit i hlavní konverzaci (1 500 čtení 48 snímků). Pravidla níže to brání; zadání piš podle vzoru.

## Rozpočet snímků
- **Nejvýš 15 snímků na pomocníka**, každý čtený **jednou** (do toho počítej i vlastní výřezy a dlaždice – každý
  obrázek je jedno čtení). Do jednoho požadavku se vejde jen asi 40 obrázků; nad tím Claude Code nejstarší vyhodí
  (v konverzaci zůstane „[media removed: request limit]“), cache se zneplatní a celý kontext se zapisuje znovu –
  cena na snímek pak roste kvadraticky.
- Víc snímků = víc pomocníků **po sobě**, každý s vlastním výstupním souborem, ne jeden velký.
- Hlídač čtení (`tools/hlidac_cteni.py`, zapíná `novy_projekt.py --hlidac`) je jen pojistka: pomocníkovi zamítne
  třetí čtení téhož obrázku a víc než 30 čtení.
- Pomocníka, kterého zastavil limit („hit your limit“) nebo hlídač, **znovu nepouštěj**. Zbytek rozděl na menší
  zadání a pusť až po obnovení limitu.

## Čtení snímků (měřeno na kurentu 1765–1831, upstream #43)
- Čti jen z **plného rozlišení** (ARON úroveň `0`, bez `nahled`).
- **Obrázek nad 1568 px na delší straně nástroj Read potichu zmenší.** Široký výřez (dvoustrana, řádek přes celou
  šířku) rozřež na dlaždice do 1568 px: `overit.py` (dvě poloviny), sloupce `mapa_knihy.py … --sloupce`, nebo
  `magick x.jpg -crop 2x1@ +repage -resize "1568x1568>" pracovni/x_dl_%d.jpg`. Přesnost čtení tím stoupla o 7–15 bodů.
- Vyšší úsilí (effort) čtení nezlepšuje. **Haiku na kurent nestačí** (34 % proti 80 % u Opusu) – pomocníci na Sonnetu,
  špatně čitelný kurent a hledání bez rejstříku silnějšímu modelu. Žádný model nečte příjmení v kurentu spolehlivě.

## Vzor zadání
Zkopíruj, doplň `<…>` a nehodící se řádky smaž. Nikdy nepiš „když se snímek nenačte, zkus to znovu“.

```
Úkol: najdi <koho; co o něm víme: rodiče, dům, roky> v <svazek, archiv, apu nebo odkaz>.
Struktura pramene: <co je v kterém sloupci; řazení po vsích; rejstřík jen zemřelých / společný; folio × snímek>.
Snímky – uzavřený seznam, jiné nečti: <cesty k souborům nebo čísla snímků, nejvýš 15>.
Kontrolní zápis: na snímku <n> je <známý zápis: jméno, datum>. Přečti ho jako první a vypiš, co v něm vidíš.
  Když ho nenajdeš nebo přečteš jinak, napiš to na začátek výsledku.
Pravidla:
- Každý snímek čti nejvýš jednou, v plném rozlišení; obrázek širší než 1568 px rozřež na dlaždice (<příkaz>).
- Když se snímek nezobrazí (chyba, „media removed“, prázdný obrázek), nečti ho znovu: zapiš ho jako NEPŘEČTENÝ
  a pokračuj dalším.
- Nikdy nepiš o snímku, který jsi neviděl, a nic nedoplňuj podle sousedních snímků nebo podle toho, co čekáš.
  Nejisté čtení označ „(?)“, nečitelné „[…]“.
- <Čísla domů: ves se <rok> přečíslovala – před ním čti čp. jako staré, po něm jako nové; neporovnávej je přímo.>
- Po každém snímku hned připiš řádek do pracovni/pom_<větev>/vysledek.md:
  snímek | stav (přečteno / nečitelné / NEPŘEČTENÝ) | rok, první a poslední jméno | nálezy (souřadnice zápisu
  x0,y0,x1,y1 jako zlomky 0–1, přepis) | související výskyty (vzácné příjmení rodu, stejný dům).
- Když hlídač čtení další čtení zamítne, skonči a vrať, co máš.
- Píšeš jen do pracovni/pom_<větev>/, do data/ nikdy. Síť jen přes python3 -I tools/slusne.py …;
  hláška „zastavený“ = skonči a ohlas to.
- <technické pasti z reference/matriky.md pro macOS nebo Windows>
Výsledek: obsah souboru vysledek.md, seznam NEPŘEČTENÝCH snímků a čtení kontrolního zápisu.
```

## Po návratu pomocníka
- **Výsledek přerušeného běhu je neověřený** (limit, chyba, hlídač): snímky bez řádku ve `vysledek.md` ber jako
  neprošlé, i když souhrn tvrdí opak.
- Kontrolní zápis nepřečetl správně → jeho záporné výsledky neplatí.
- Nepřečtené snímky dej dalšímu pomocníkovi nebo si je přečti sám – ne témuž pomocníkovi znovu.
- Záporný výsledek a čtení pomocníka přijmi jen podle pravidel v `SKILL.md` → Pomocníci (doklad, `overit.py`).
