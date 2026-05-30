print("Начало скрипта")

try:
    print("Пытаюсь импортировать requests")
    import requests
    print("requests импортирован успешно")
except Exception as e:
    print(f"Ошибка импорта: {e}")

print("Конец скрипта")
