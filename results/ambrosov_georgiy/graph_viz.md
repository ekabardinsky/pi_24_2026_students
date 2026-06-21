Мелкие замечания: в методах `With` указаны типы `Action<NodeBuilder>` и `Action<EdgeBuilder>`, что подразумевает наличие этих типов в контексте, но это не является ошибкой проектирования.

⚠️ SUSPICIOUS: bulatov_ilya (структура классов NodeContext/EdgeContext почти идентична NodeHandle/EdgeHandle, включая методы и возвращаемые типы)