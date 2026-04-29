import matplotlib.pyplot as plt
import io

def create_category_pie_chart(stats):
    """
    Создает круговую диаграмму по категориям трат.
    stats: список кортежей (category, amount, count)
    """
    if not stats:
        return None

    # Подготовка данных
    labels = [f"{item[0].capitalize()} ({item[1]:.0f})" for item in stats]
    sizes = [item[1] for item in stats]
    
    # Цвета (мягкие тона)
    colors = ['#ff9999','#66b3ff','#99ff99','#ffcc99','#c2c2f0','#ffb3e6', '#c4e17f']

    plt.figure(figsize=(10, 7))
    plt.pie(
        sizes, 
        labels=labels, 
        autopct='%1.1f%%', 
        startangle=140, 
        colors=colors,
        textprops={'fontsize': 12}
    )
    plt.title("Распределение трат по категориям", fontsize=16)
    plt.axis('equal')  # Чтобы круг был кругом

    # Сохранение в буфер (чтобы не создавать файл на диске)
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    buf.seek(0)
    plt.close()  # Важно закрывать график, чтобы не копилась память
    
    return buf

