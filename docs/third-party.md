# Приложения в архиве

Google Services Framework, Google Play Services, Play Маркет и LeanKeyboard сохраняют исходные идентификаторы и подписи. YouTube Fix описан отдельно ниже. Переведённые приложения Dangbei подписаны отдельным ключом и устанавливаются под отдельными именами пакетов. Ключ подписи в репозитории и архиве отсутствует.

В русификацию входят:

- `com.dangbei.launcher3`, русский лаунчер на базе штатного 2.4.2.
- `local.dangbei.settings.ru`, настройки на базе x5u_50000_A3F9EA2.
- `local.dangbei.sidebar.ru`, боковая панель на базе X5U_41001_295FA2C.
- `local.dangbei.colormaster.ru`, Мастер изображения на базе 5.0.0.3_B4A2D7E.
- `local.ru.db.screencast`, Трансляция на базе Dangbei Cast v2.8.7.9.
- `local.dangbei.settings.writer`, служебный модуль для записи настроек изображения. У него нет отдельного экрана.
- [LeanKeyboard 6.1.31](https://github.com/yuliskov/LeanKeyboard/releases/tag/6.1.31), клавиатура для Android TV. [Лицензия автора](LeanKeyboard-LICENSE.txt) приложена к архиву.

При выборе Google дополнительно устанавливаются:

- Google Services Framework 11, код версии 30. APK из [Open GApps для Android 11](https://sourceforge.net/projects/opengapps/files/arm64/20220503/).
- Google Play Services 25.16.33 (180306-750736914), код версии 251633118. Установленный вариант использует armeabi-v7a, проверен на Android 11 этого проектора.
- Google Play Маркет 50.4.14-24 [8] [PR] 876411324, код версии 85041408. В архиве три части одной установленной сборки: основной APK, ARM64 и русский язык. Установщик передаёт их ADB одной командой.

При выборе YouTube Fix устанавливается отдельный пакет `local.ru.youtube.tv` на базе YouTube TV 7.32.300, armeabi-v7a, код версии 732300320. Исходный APK Google проверен по подписи, его SHA-256 закреплён в скрипте сборки. Исправленная копия подписана ключом проекта, YouTube остаётся приложением Google, лицензия установщика на него не распространяется.

Метод подключения фильтра к Cobalt основан на [FaroTV](https://github.com/jair1c/farotv-patches/tree/8478a5a4dfbe6b315fce31d76d5c40986bbae5d6) и [ysamjo/morphe-patches](https://github.com/ysamjo/morphe-patches/tree/74c4272edb6b82219926d7f6e75ef4347c06663d). Исходники локальной адаптации, фильтр, служба восстановления исключений и GPL-3.0 находятся в `patches/youtube-fix`, они приложены к готовым комплектам. Исходный APK Google и ключ подписи в исходники не входят.

Версии закреплены в `manifest.json`. Скрипт не ищет случайные последние APK в интернете. Контрольные суммы проверяются до установки, а затем ещё раз для установленных файлов.

После запуска Google может обновить свои приложения сам. Если на проекторе уже стоит более новая версия Google, установщик сохраняет её и не понижает.

В готовые комплекты для компьютера также входят Python, загрузчик PyInstaller и Android Platform Tools 36.0.2. Они запускаются из распакованной папки. Лицензии Python и PyInstaller находятся в `docs`, сведения об Android Platform Tools в `platform-tools/NOTICE.txt`. Исходные ссылки и контрольные суммы Platform Tools закреплены в `scripts/platform-tools.json`, сведения о конкретной сборке лежат в `build-info.json`.
