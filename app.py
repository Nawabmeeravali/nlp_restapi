from flask import Flask, jsonify, request
import pickle
import os
#import pandas as pd
#import numpy as np

from tensorflow.python.keras import models, layers, optimizers
import tensorflow
from tensorflow.keras.preprocessing.text import Tokenizer, text_to_word_sequence
from tensorflow.keras.preprocessing.sequence import pad_sequences

MAX_LENGTH=254
MAX_FEATURES = 10000
tokenizer = pickle.load(open('models/tokenizer.pkl','rb'))


def build_lstm_model():
    sequences = layers.Input(shape=(MAX_LENGTH,))
    embedded = layers.Embedding(MAX_FEATURES, 64)(sequences)
    x = layers.LSTM(128, return_sequences=True)(embedded)
    x = layers.LSTM(128)(x)
    x = layers.Dense(32, activation='relu')(x)
    x = layers.Dense(100, activation='relu')(x)
    predictions = layers.Dense(1, activation='sigmoid')(x)
    model = models.Model(inputs=sequences, outputs=predictions)
    model.compile(
        optimizer='rmsprop',
        loss='binary_crossentropy',
        metrics=['binary_accuracy']
    )
    return model
    
lstm_model = build_lstm_model()

lstm_model.load_weights('models/lstm.h5')


#f=['pleasant experience i will buy one more good']
#f=tokenizer.texts_to_sequences(f)
#f=pad_sequences(f,maxlen=MAX_LENGTH)
#print(lstm_model.predict(f))

def predict(l):
    x=[l]
    f=tokenizer.texts_to_sequences(x)
    f=pad_sequences(f,maxlen=MAX_LENGTH)
    x=str(lstm_model.predict(f)[0])
    return x


app = Flask(__name__)
@app.route('/nlp', methods=['GET', 'POST'])
def add_message():
    content = request.json
    px=content['text']
    #print(type(content['text']))
    return jsonify({"sentiment": predict(px) })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0',port=port,debug=True, use_reloader=True)