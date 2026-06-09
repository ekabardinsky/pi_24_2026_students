# Массив с парами "имя_файла:Название_Класса"
solutions=(
    "sboi.cs:Sboi"
    "homm.cs:HoMM"
    "geometry-2.cs:Geometry2"
    "robots.cs:Robots"
    "report_generator.cs:ReportGenerator"
    "diff.cs:Diff"
    "taxi_order.cs:TaxiOrder"
    "graph_viz.cs:GraphViz"
    "razriad.cs:Razriad"
    "painter.cs:Painter"
)

echo "Generating reference solution files in reference_solutions/..."

# Цикл по всем элементам массива
for item in "${solutions[@]}"; do
    filename="${item%%:*}"
    classname="${item##*:}"
    
    # Создаем .cs файл с базовой структурой
    cat << EOF > "reference_solutions/$filename"
namespace Practice.ReferenceSolutions
{
    public class $classname
    {
        // TODO: Реализовать эталонное решение задачи
    }
}
EOF
    echo "  -> Created reference_solutions/$filename"
done

echo "All reference solution files successfully created!"
