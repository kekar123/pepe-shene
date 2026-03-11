Поместите PNG-файлы символов в эту папку.

Поддерживаемые типы и имена файлов:

1) EAC
- eac.png

2) Бокал/вилка
- glass.png
- fragile.png
- glass_fork.png

3) PP5
- pp5.png
- recycle_pp5.png
- mobius_pp5.png

4) PET1
- pet1.png
- recycle_pet1.png
- mobius_pet1.png
- 01_pet.png

Как это работает:
- В UI отмечаете чекбокс символа.
- Сервер передает graphic_symbols в layout.
- Layout ищет соответствующий PNG в этой папке и ставит его на этикетку.

Если файл не найден, вместо картинки рисуется fallback-плашка с названием символа.
