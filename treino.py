import pandas as pd
import pickle
from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score

from config import attributes, label, caminho_dataset, caminho_modelo

# 1.Carregando e preparando dados

df = pd.read_csv(caminho_dataset)

# seleciona as colunas de entrada
X = df[attributes]

# Converte o rótulo para binário: 1 = irregular, 0 = regular
# Necessário pois algoritmos de ML trabalham com números, não texto
y = (df[label] == 'irregular').astype(int)


# 2.Treino(80%) e Teste(20%)

X_train, X_test, y_train, y_test = train_test_split(
    X, y,
    test_size= 0.2,
    random_state= 42,
    stratify= y
)
print('Visualização das amostras:\n')
print(f'Treino: {len(X_train)} amostras')
print(f'Teste: {len(X_test)} amostras')


# 3. Treino do modelo

# cria modelo com 100 árvores de precisão
# Mais árvores = mais robustos, necessário mais tempo para treinar (treinamentos mais lento)
modelo = RandomForestClassifier(
    n_estimators= 100,
    class_weight='balanced',
    random_state= 42
)

modelo.fit(X_train, y_train)

# 4. Avaliação / Cross Validation

# 5 divisões estratificadas e embaralhadas
# Mede se o modelo generaliza bem ou está "decorando" os dados de treino
cv = StratifiedKFold(n_splits= 5, shuffle= True, random_state= 42)

# F1 é a média harmônica entre precisão e recall
# Boa métrica para classes desbalanceadas (mais regulares do que irregulares)
cv_scores = cross_val_score(modelo, X_train, y_train, cv=cv, scoring = 'f1')

print('\nValidação Cruzada:')
print(f'Cross-Validation F1 (5-fold): {cv_scores.mean():.4f} ± {cv_scores.std():.4f}')

# 5. Avaliar - Conjunto Teste

# Gera predições para os dados de teste (nunca vistos durante o treino)
y_pred = modelo.predict(X_test)

# Percentual de classificações corretas sobre o total
print(f'\nAcurácia no Teste: {accuracy_score(y_test, y_pred):.4f}')

# Relatório completo: precisão, recall e F1 por classe
print('\nRelatório de Classificação')
print('|', '='*50, '|')
print(classification_report(y_test,y_pred, target_names= ['regular', 'irregular']))

# Cálculo da matriz de confusão: onde acertou e onde errou
cm = confusion_matrix(y_test, y_pred)
print(f'Matriz de Confusão:')
print(f'{cm}')
print('INTERPRETAÇÃO')
print(f'Verdadeiro Regular: {cm[0,0]}')
print(f'Falso Irregular: {cm[0,1]}')
print(f'Falso Regular: {cm[1,0]}')
print(f'Verdadeiro Irregular: {cm[1,1]}')

# 6. Importância dos Atributos
print('\nImportância dos Atributos:')

fi = pd.Series(modelo.feature_importances_, index = attributes).sort_values(ascending= False)
for feat, imp in fi.items():
    barra = '█' * int(imp * 30)           # barra visual proporcional à importância
    print(f"  {feat:<30} {imp:.4f}  {barra}")

# 7. Salvando o modelo

# Abre o arquivo de destino em modo de escrita binária
with open(caminho_modelo, 'wb') as f:
    pickle.dump({'modelo': modelo, 'atributos': attributes}, f)

print(f'\n Modelo salvo com sucesso em {caminho_modelo}!')