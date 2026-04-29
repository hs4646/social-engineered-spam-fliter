# Manglish and Shortlink Detection Upgrade

## Goal

Improve the phishing detection engine so it:

- detects Manglish scam messages more reliably,
- treats shortlinks and suspicious domains as explicit signals,
- continues using the existing TF-IDF + Random Forest + SVM scoring flow,
- learns from English scam messages and Malay scam messages in one shared dataset.

## Current State

The current engine in `app/services/learning_engine.py` trains directly on raw `content` text using:

- `TfidfVectorizer`
- `RandomForestClassifier`
- `SVC`

The main weakness is that the feature pipeline is almost entirely lexical. It does not explicitly model:

- Manglish spelling variation,
- shortlink presence,
- suspicious domain patterns,
- URL-brand mismatch,
- urgency and credential-theft style cues beyond what TF-IDF happens to learn.

## Scope

This change covers:

- preprocessing and feature engineering in the training/scoring pipeline,
- dataset consolidation rules for English, Malay, and Manglish samples,
- tests for multilingual and shortlink-heavy examples.

This change does not cover:

- live URL expansion over the network,
- browser-side link reputation lookup,
- replacing the current RF/SVM model family,
- dashboard UI redesign.

## Approach

### 1. Manglish-Aware Normalization

Add a normalization layer before TF-IDF vectorization.

The normalizer will:

- lowercase text,
- normalize repeated whitespace,
- preserve URLs for separate URL feature extraction,
- map common Manglish shorthand and noisy spellings into canonical tokens,
- emit both the original cleaned text and the normalized text signal for stronger feature coverage.

Examples of normalization targets:

- `u` -> `you`
- `ur` -> `your`
- `x` -> `tak` or `tidak` depending on the token pattern chosen for consistency
- `pls` -> `please`
- `sy` / `sya` / `aq` -> `saya`
- `ni` -> `ini`
- `je` / `jer` -> `sahaja`
- `blh` -> `boleh`
- `jgn` -> `jangan`
- `nnti` -> `nanti`
- `kene` -> `kena`

The mapping will be intentionally small and maintainable. The first version should focus on frequent scam and chat abbreviations rather than trying to normalize all colloquial Malay.

### 2. Explicit URL and Domain Features

Add a handcrafted feature extractor that derives numeric and boolean signals from message text.

Initial features:

- `has_url`
- `url_count`
- `has_shortlink`
- `shortlink_count`
- `has_suspicious_tld`
- `has_ip_address_url`
- `has_non_http_like_link_pattern`
- `has_brand_name`
- `has_brand_domain_mismatch`
- `has_urgent_phrase`
- `has_money_phrase`
- `has_account_threat_phrase`
- `has_action_phrase`

Shortlink detection should explicitly flag common shortening domains such as:

- `bit.ly`
- `tinyurl.com`
- `t.co`
- `goo.gl`
- `cutt.ly`
- `rb.gy`
- `shorturl.at`

Suspicious domain heuristics should include:

- uncommon or misleading TLDs in this dataset context,
- excessive hyphenation,
- domains pretending to be banks, delivery services, government portals, or university systems without matching official hostnames.

### 3. Shared Multilingual Training Data

The engine will continue to train from a single `content,label` dataset, but the dataset preparation must better represent:

- English scam messages,
- Malay scam messages,
- normal English messages,
- normal Malay messages,
- normal Manglish chat,
- scam messages written in Manglish or mixed Malay-English style.

The merged training dataset should become the canonical source for the app runtime. Existing source CSVs may still be retained as raw inputs, but training should not depend on ad hoc file selection.

### 4. Keep Current Model Flow

The model architecture remains:

- TF-IDF text features
- Random Forest classifier
- SVM classifier
- average of RF and SVM probabilities for final risk score

The key change is that TF-IDF should be combined with engineered URL/risk features in one feature matrix before model fitting and inference.

### 5. Light Heuristic Boost

Add a small post-model risk adjustment for high-confidence shortlink abuse cases.

This is intentionally limited. It should only increase risk when multiple suspicious signals co-occur, for example:

- shortlink + urgent action phrase,
- shortlink + brand mismatch,
- shortlink + account restriction language.

The heuristic must not dominate the classifier. Its role is to improve precision on obvious phishing patterns the current lexical model tends to underweight.

## Architecture Changes

### Training Pipeline

`app/services/learning_engine.py` will be expanded to:

1. load and validate the dataset,
2. normalize message text,
3. extract URL/domain/risk features,
4. vectorize normalized text with TF-IDF,
5. combine sparse text features with dense handcrafted features,
6. train RF and SVM on the combined feature matrix,
7. return the fitted preprocessing assets and model metrics.

The returned model bundle should include:

- text vectorizer,
- feature extractor configuration,
- RF model,
- SVM model,
- metrics,
- model version metadata.

### Inference Pipeline

`ModelRegistry.score()` and the radar worker should use the same preprocessing steps as training:

1. normalize the incoming message,
2. extract handcrafted features,
3. transform TF-IDF text,
4. combine features,
5. score with RF and SVM,
6. apply the light heuristic boost,
7. return final risk plus component scores.

## Dataset Rules

The canonical training CSV must:

- keep `content,label` as required columns,
- preserve both label classes `0` and `1`,
- avoid empty rows,
- include enough examples for each language/register combination,
- include legitimate messages that also contain links so the engine does not learn `any link = scam`.

Important negative examples to add:

- legitimate shortlinks used in harmless contexts,
- legitimate Malay reminders containing links,
- casual Manglish conversations with abbreviations but no scam intent.

Important positive examples to add:

- shortlink-based phishing,
- fake account restriction notices,
- fake delivery fee requests,
- fake government or university portal prompts,
- mixed-language scams using urgency and payment prompts.

## Testing Strategy

Add tests that verify:

- a Manglish scam message scores higher than a normal Manglish chat,
- a suspicious shortlink message scores as high risk,
- a legitimate shortlink message is not automatically treated as phishing,
- multilingual dataset loading still works,
- model training returns the expected bundle shape and metrics.

Tests should stay deterministic and use temporary CSV datasets built inside the test suite.

## Risks and Mitigations

### Risk: Overfitting shortlinks

If every shortlink is treated as suspicious, legitimate shortlinks will be over-penalized.

Mitigation:

- include legitimate shortlink negatives,
- require multiple suspicious signals before heuristic boosting,
- test both malicious and legitimate shortlink cases.

### Risk: Over-normalizing Manglish

Aggressive replacement could distort innocent messages or remove useful clues.

Mitigation:

- keep the mapping small,
- preserve the raw lexical content through the original cleaned text signal,
- add tests for normal Manglish chat.

### Risk: Sparse feature mismatch between training and inference

If handcrafted features are not generated identically in both places, scoring will break or drift.

Mitigation:

- centralize preprocessing in shared helpers inside the learning engine module,
- ensure both training and scoring use the same path.

## Success Criteria

The upgrade is successful when:

- the engine can better separate scam vs legitimate Manglish messages,
- explicit shortlink/domain signals materially influence scoring,
- the current runtime flow remains intact,
- tests cover the new multilingual and shortlink behavior,
- the app still trains and scores through the existing service boundary.
