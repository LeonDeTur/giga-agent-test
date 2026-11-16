# Сборка установщика ДПО

Требуется Inno Setup 6. Из корня репозитория запустите:

~~~cmd
bundle\installer\build.cmd
~~~

Результат: bundle\dist\dpo-giga-agent-setup.exe и файл рядом с ним
bundle\dist\dpo-giga-agent-setup.exe.sha256 (SHA256 готового exe).
Без DPO_SIGN_CMD сборка не подписывается; ошибки возвращают ненулевой код.

Для подписи нужен signtool.exe из Windows SDK в PATH и доступный сертификат.
В cmd задайте шаблон с RFC 3161 timestamp и запустите ту же сборку:

~~~cmd
set "DPO_SIGN_CMD=signtool.exe sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 /a $f"
bundle\installer\build.cmd
~~~

Подписываются установщик и деинсталлятор; SHA256 вычисляется после подписи.
Для путей с пробелами используйте $q вместо кавычек в шаблоне Inno Setup.
Для доверенного издателя нужен доверенный Windows сертификат подписи кода
OV/EV или сервис подписи; самоподписанный сертификат не помогает на чужих ПК.
Подпись не гарантирует исчезновения SmartScreen: учитывается и репутация файла.

После проверки опубликуйте оба файла:

~~~cmd
gh release create v1.0.0 bundle/dist/dpo-giga-agent-setup.exe bundle/dist/dpo-giga-agent-setup.exe.sha256
~~~

Полная инструкция: [Установка и сборка комплекта](../docs/01_install_and_build.md).
