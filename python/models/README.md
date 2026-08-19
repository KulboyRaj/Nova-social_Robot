# models/

This folder is where locally-trained/downloaded model weights live. It is
intentionally **not** populated by this repo or by `pip install`, because
model weight files are large, project-specific, and (for FER2013) require
you to either train the CNN yourself or fetch someone's pre-trained
weights under whatever license they publish them.

## Required file

**`emotion_model.h5`** — a Keras CNN trained on FER2013 (48x48 grayscale
input, 7-class softmax output in this order: `Angry, Disgust, Fear, Happy,
Sad, Surprise, Neutral`). This matches the AI/ML table in the project
report (TensorFlow/Keras, FER2013, 35,887 images).

`python/perception/emotion.py` will automatically load this file if
present. **If it's missing, the app still runs** — it falls back to a
much simpler OpenCV smile-detector heuristic (Happy vs Neutral only) so
the demo isn't blocked, but that fallback is not the CNN your report
describes and won't hit the accuracy numbers you wrote down.

### Option A — train it yourself (matches the report exactly)
1. Download FER2013 (`fer2013.csv`) from Kaggle:
   `https://www.kaggle.com/datasets/msambare/fer2013` (Kaggle account
   required; dataset is user-uploaded from the original ICML 2013
   challenge).
2. Train a small CNN (Conv2D/MaxPool/Dropout stack -> Dense(7, softmax))
   with TensorFlow/Keras. Many public notebooks named "FER2013 Keras CNN"
   walk through this in under an hour on a free Colab GPU.
3. `model.save("emotion_model.h5")` and copy it into this folder.

### Option B — use a pre-trained public checkpoint
Several MIT/BSD-licensed FER2013 Keras checkpoints exist on GitHub (search
"FER2013 keras h5 pretrained"). Verify the license before using one in a
public submission, and double check the class order matches the list
above (some repos order classes differently).

### Where this file needs to end up on the actual board
Copy it to `python/models/emotion_model.h5` inside the app folder that
gets pushed to the UNO Q (e.g. `~/ArduinoApps/nova-robot/python/models/`
if you're using the CLI/`scp` workflow described in the project README).
