# Corrida archivada: juez v1 (Qwen2.5-1.5B-Instruct)

Esta carpeta guarda la **primera corrida del harness**, con la versión 1 del juez. Se conserva
como evidencia de por qué la Dimensión 2 se rehizo. La explicación completa está en la sección
7.0 del notebook.

## Qué falló

El juez le puso **la misma nota a los tres sistemas en los 13 casos**:

| | BM25 | E5 congelado | E5 ajustado |
|---|---|---|---|
| LLM-juez, todo | 3,46 | 3,46 | 3,46 |
| LLM-juez, gold | 4,20 | 4,20 | 4,20 |
| LLM-juez, adversarial | 1,00 | 1,00 | 1,00 |

No estaba leyendo los resultados. La prueba de discriminación lo detectó sola: ordenamiento
oráculo 5/5, ordenamiento invertido 5/5, **contraste 0**. El pairwise respondió "B" en las 10
comparaciones, en los dos órdenes.

## Las tres causas

1. **El `criterio` del equipo iba al final del prompt y decidía la nota.** Los casos que sacaron
   1 (`pasteles sin azucar`, `matrix triologia`, y los tres adversariales) son justamente
   aquellos cuyo criterio contiene "no se pidió", "no debería", "Falla si". El modelo leía la
   cola del prompt, no la lista de productos.
2. **Generar texto y quedarse con el primer dígito es frágil**, y con un modelo pequeño colapsa a
   una respuesta constante.
3. **La abstención le pedía una inferencia de dos pasos** que un modelo de 1.5B no hace: le puso
   1/5 a una abstención correcta, que según la rúbrica valía 5.

## Qué sí sirve de esta corrida

Las Dimensiones 1 y 3 de esta corrida son válidas y coinciden con las de la corrida definitiva:
el juez no interviene en ninguna de las dos.

| | BM25 | E5 congelado | E5 ajustado |
|---|---|---|---|
| nDCG@10 (10 gold) | 0,660 | 0,721 | 0,834 |
| Aciertos gold (top-3) | 6/10 | 7/10 | 8/10 |
| Abstención adversarial | 0/3 | 1/3 | 3/3 |
