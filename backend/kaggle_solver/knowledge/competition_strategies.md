# Kaggle Competition Strategies

## General Workflow

### Phase 1: Understanding the Problem (Day 1-2)
1. Read competition description carefully — understand the metric.
2. Explore the data: shape, dtypes, missing values, distributions.
3. Read top forum posts and notebooks from similar past competitions.
4. Understand the evaluation metric deeply.
5. Check for data leakage opportunities (sometimes intentional in competitions).

### Phase 2: Baseline (Day 2-3)
1. Build a simple baseline: mean prediction, simple model.
2. Set up cross-validation that matches the leaderboard.
3. Verify CV score correlates with LB score.
4. Submit baseline to understand LB position.

### Phase 3: Feature Engineering (Day 3-10)
1. Explore feature importance from baseline model.
2. Create domain-specific features.
3. Add aggregation features (group statistics).
4. Handle missing values thoughtfully.
5. Validate each feature addition with CV.

### Phase 4: Model Tuning (Day 10-20)
1. Tune hyperparameters with Optuna.
2. Try different model architectures.
3. Experiment with different preprocessing.
4. Build diverse models for ensembling.

### Phase 5: Ensembling (Final Days)
1. Ensemble best models.
2. Optimize ensemble weights.
3. Post-process predictions.
4. Final submissions: best single model + best ensemble.

## Evaluation Metrics

### Classification Metrics
- **AUC-ROC**: Area under ROC curve. Threshold-independent. Use for binary classification.
- **Log Loss**: Penalizes confident wrong predictions. Calibrate probabilities.
- **F1 Score**: Harmonic mean of precision and recall. Good for imbalanced classes.
- **Accuracy**: Simple but misleading for imbalanced datasets.
- **Cohen's Kappa**: Agreement metric, used in medical/NLP competitions.
- **MAP@K**: Mean Average Precision at K. Used in recommendation systems.

### Regression Metrics
- **RMSE**: Root Mean Squared Error. Penalizes large errors heavily.
- **MAE**: Mean Absolute Error. More robust to outliers than RMSE.
- **RMSLE**: Root Mean Squared Log Error. Use log1p transform on target.
- **R²**: Coefficient of determination. 1.0 = perfect, 0 = mean prediction.
- **MAPE**: Mean Absolute Percentage Error. Scale-independent.

### Optimizing for Specific Metrics
- For RMSE: minimize squared errors, outliers matter.
- For MAE: use quantile regression (q=0.5), more robust.
- For AUC: threshold doesn't matter, focus on ranking.
- For Log Loss: calibrate probabilities, avoid extreme predictions.
- For F1: optimize classification threshold on validation set.

## Cross-Validation Strategy

### Matching CV to LB
- If LB uses random split: use StratifiedKFold.
- If LB uses time split: use TimeSeriesSplit.
- If LB uses group split: use GroupKFold.
- Always verify CV-LB correlation before trusting CV.

### Detecting CV-LB Discrepancy
- If CV improves but LB doesn't: overfitting to CV, or CV doesn't match LB split.
- If LB improves but CV doesn't: possible data leakage or different distributions.
- Use public LB as additional validation signal, not primary metric.

## Handling Imbalanced Data
- **Oversampling**: SMOTE, ADASYN — generate synthetic minority samples.
- **Undersampling**: Random undersampling of majority class.
- **Class weights**: `class_weight='balanced'` in sklearn, `scale_pos_weight` in XGBoost.
- **Threshold tuning**: Find optimal threshold on validation set.
- **Stratified sampling**: Always use stratified CV for imbalanced data.

## Data Leakage Detection
- Check if test data has information from the future.
- Look for ID columns that encode target information.
- Check if row order matters (time-based leakage).
- Validate that features are available at prediction time.
- Common leakage: using future aggregations, target-correlated IDs.

## Pseudo-Labeling
1. Train model on labeled data.
2. Predict on test data with high confidence.
3. Add high-confidence test predictions as training data.
4. Retrain model on combined data.
5. Repeat 2-3 times.
- Works best when test distribution differs from train.

## Test Time Augmentation (TTA)
- For images: flip, rotate, crop, then average predictions.
- For tabular: add small noise to features, average predictions.
- For text: paraphrase, back-translate, then average.

## Shake-Up Prevention
- Don't overfit to public LB (only ~30% of test data).
- Trust your CV score more than public LB.
- Submit diverse solutions: best CV + best LB + ensemble.
- Keep 2 final submission slots for safe choices.

## Competition-Specific Tips

### Tabular Competitions
- LightGBM is almost always the best starting point.
- Feature engineering matters more than model tuning.
- Ensemble LightGBM + XGBoost + CatBoost + Neural Net.
- Target encoding with proper CV is very powerful.

### NLP Competitions
- Fine-tune pretrained transformers (BERT, RoBERTa, DeBERTa).
- Ensemble multiple transformer architectures.
- Use different tokenizers and max lengths.
- Multi-task learning if multiple targets available.

### Computer Vision Competitions
- Start with EfficientNet or ViT.
- Heavy augmentation (Albumentations library).
- Test Time Augmentation (TTA).
- Pseudo-labeling on test data.

### Time Series Competitions
- Feature engineering: lags, rolling statistics, Fourier features.
- LightGBM with lag features often beats LSTM.
- Temporal Fusion Transformer for complex patterns.
- Careful with CV: always use time-based splits.

## Forum and Discussion Strategy
- Read all forum posts in first 2 days.
- Share insights to get karma and access to others' insights.
- Look for data quality issues reported by others.
- Check if there are known data leaks.
- Follow top competitors' public notebooks.
