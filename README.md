# THE HOUR AFTER MIDNIGHT — инструменты канала

Скрипты для монтажа хоррор-шортсов и длинных видео: убрать водяной знак,
склеить куски, добавить плашки, сделать субтитры по голосу, покрасить в стиль канала.

## Установка (один раз)

Нужны `ffmpeg` и Python 3.

```bash
bash tools/setup_models.sh      # Python-пакеты + модель распознавания речи (~650 МБ)
```

## 1. Убрать водяной знак «Dola AI»

Находит знак сам, даже если он прыгает по кадру.

```bash
python3 tools/remove_watermark.py кусок.mp4 кусок_clean.mp4
```

## 2. Собрать шортс из кусков

```bash
python3 tools/assemble_short.py -o part2.mp4 \
  --clip кусок1_clean.mp4:3.0 --clip кусок2_clean.mp4 \
  --top "Part 2. 3:13 AM. Bedroom camera" --top-until 3.6 \
  --end "Which one did I marry?" --end-from 26
```

- `--clip файл:начало:конец` — секунды, начало/конец можно не указывать.
- `--top` — плашка сверху слева в начале; `--end` — плашка снизу в финале.
- В конце добавляется 2,2 с чёрного экрана (`--tail`).

## 3. Субтитры по голосу (длинные видео)

Текст берётся из сценария (без ошибок), время — по голосу.

```bash
python3 tools/subtitles.py --audio озвучка.mp3 --script сценарий.txt --lang ru --out palata9
# palata9.srt — загрузить на YouTube; palata9.ass — вшить в видео
```

## 4. Стиль канала для длинного видео

Холодный цвет, зерно, виньетка, вшитые субтитры. Камеру не трясём.

```bash
bash tools/grade.sh монтаж.mp4 final.mp4 palata9.ass
```

### Таймкод камеры

Если на кадре «с записи» стоит дневное время, закройте его ночным
(пример — 1080p, надпись в правом верхнем углу, показывается 153.5–157.75 с):

```bash
EN="between(t,153.5,157.75)"
ffmpeg -i in.mp4 -vf "drawbox=x=1300:y=24:w=592:h=54:color=0x0b0b0b@0.92:t=fill:enable='$EN',\
drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf:text='REC':fontsize=38:fontcolor=0xd23a2f:x=1322:y=31:enable='($EN)*lt(mod(t\,1)\,0.65)',\
drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf:text='14-11-2024':fontsize=38:fontcolor=0xeeeeee:x=1422:y=31:enable='$EN',\
drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf:text='%{pts\:gmtime\:11407\:%H\\\:%M\\\:%S}':fontsize=38:fontcolor=0xeeeeee:x=1684:y=31:enable='$EN'" out.mp4
```
`11407` = (03:12:41 в секундах) − (время появления надписи). Подставьте своё.

---

## Правила генерации (что работает)

- **Генератор выдаёт 15 секунд за раз**, даже если пишет «30s». Шортс = 2 куска по 15 с.
- **Одно событие на кусок.** Кусок 1 — «всё спокойно», кусок 2 — одно событие.
- **В первом куске прямо пишите, чего НЕТ:** *"nobody else in the room, no shadows, no figures"*.
- **Image-to-Video, а не Text-to-Video.** Стартовый кадр = последний кадр предыдущего куска
  (или референс комнаты). Без этого генератор рисует другую комнату.
- **Якорь** — одинаковое описание места и персонажа, копируется слово в слово в каждый промпт.
- **Камера статична:** *"static locked-off shot, the camera never moves"*.
- В конец промпта: *"No text, no timestamp, no watermark."*
- **Модерация** режет: horror/terrifying, монстров крупно, «смотрит в камеру + открывает глаза + тсс».
  Проходит: *suspenseful, mysterious, silhouette, a pale face faintly visible*.
- Пугает то, чего не видно: пустая комната и испуганное животное > «инопланетянин».

## Что уже вышло и зашло

| Серия | Формат | Результат |
|---|---|---|
| My Wife Was Asleep Next to Me (Part 1–3) | две камеры, двойник | 2 400+ просмотров, досмотр 106% |
| Dogs See What We Can't | «Case N», животное видит лицо в двери | 900+ |
| I Live Alone. My Fridge Opened by Itself | кухня, холодильник | 480+ |
| Палата девять / Room 9 | длинное, картинки + озвучка | RU и EN версии |

Плашки серии: светло-серый скруглённый фон, тёмный текст (Inter Medium), сверху слева —
«Part N. 3:12 AM. Bedroom camera», в финале снизу по центру — короткая фраза-крючок.
