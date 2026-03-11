import requests

# Проверяем генерацию
response = requests.post('http://localhost:8000/api/generate', json={
    'text': 'Тестовый товар',
    'size_id': '46x46',
    'preview_mode': True
})
print(response.json())

# Проверяем, создался ли файл
import os
if os.path.exists('output/preview_46x46.png'):
    print('✅ Файл создан:', os.path.getsize('output/preview_46x46.png'), 'байт')
else:
    print('❌ Файл не создан')