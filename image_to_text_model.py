from keras.models import Model
from keras.layers import Input, LSTM, Dense, Embedding, Masking
from keras.optimizers import *
import numpy as np
import h5py
import json
import time
import datetime
import os
import psutil


def generate_input_from_file(file_path, vocabulary_path, batch_size):
    while 1:
        train_file = h5py.File(file_path, 'r')
        vocab_json = json.load(open(vocabulary_path))
        image_embeddings = train_file["image_embeddings"]
        story_sentences = train_file["story_sentences"]
        num_samples = len(image_embeddings)
        samples_per_story = 5

        encoder_batch_input_data = np.zeros((batch_size * samples_per_story, 5, 4096))
        decoder_batch_input_data = np.zeros((batch_size * samples_per_story, 22))
        decoder_batch_target_data = np.zeros(
            (batch_size * samples_per_story, story_sentences.shape[2], len(vocab_json['idx_to_words'])),
            dtype='float32')
        print("decoder shape", decoder_batch_target_data.shape)

        for i in range(num_samples):

            for j in range(samples_per_story):
                encoder_batch_input_data[
                ((i % batch_size) * samples_per_story): ((i % batch_size) * samples_per_story) + 5, j] = \
                    image_embeddings[i][j]
                decoder_batch_input_data[(i % batch_size) * samples_per_story + j] = story_sentences[i][j]

            story = story_sentences[i]
            for sentence_index in range(len(story)):
                sentence = story[sentence_index]
                for word_index in range(len(sentence)):
                    if word_index > 0:
                        decoder_batch_target_data[
                            ((i % batch_size) * samples_per_story) + sentence_index, word_index - 1, sentence[
                                word_index]] = 1

            if ((i + 1) % batch_size) == 0 and i != 0:
                print("yield i: ", i)
                yield ([encoder_batch_input_data, decoder_batch_input_data], decoder_batch_target_data)
                encoder_batch_input_data = np.zeros((batch_size * samples_per_story, 5, 4096))
                decoder_batch_input_data = np.zeros((batch_size * samples_per_story, 22))
                decoder_batch_target_data = np.zeros(
                    (batch_size * samples_per_story, story_sentences.shape[2], len(vocab_json['idx_to_words'])),
                    dtype='float32')


vocab_json = json.load(open('./dataset/vist2017_vocabulary.json'))
train_file = h5py.File('./dataset/image_embeddings_to_sentence/stories_to_index_train.hdf5','r')

batch_size = 13  # Batch size for training.
epochs = 2  # Number of epochs to train for.
latent_dim = 256  # Latent dimensionality of the encoding space.
word_embedding_size = 300

learning_rate = 0.001
gradient_clip_value = 5.0

num_samples = len(train_file["story_ids"])
num_decoder_tokens = len(vocab_json['idx_to_words'])

ts = time.time()
start_time = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')

# print('Vocab size: ', num_decoder_tokens)

# # Shape (num_samples, 4096), 4096 is the image embedding length
encoder_inputs = Input(shape=(None, 4096))
mask_layer = Masking(mask_value=0)
mask_tensor = mask_layer(encoder_inputs)
encoder = LSTM(latent_dim, return_state=True)
encoder_outputs, state_h, state_c = encoder(mask_tensor)
encoder_states = [state_h, state_c]

decoder_inputs = Input(shape=(22,))

embedding_layer = Embedding(num_decoder_tokens, word_embedding_size, mask_zero=True)
embedding_outputs = embedding_layer(decoder_inputs)
decoder_lstm = LSTM(latent_dim, return_sequences=True, return_state=True)
decoder_outputs, _, _ = decoder_lstm(embedding_outputs, initial_state=encoder_states)
decoder_dense = Dense(num_decoder_tokens, activation='softmax')
decoder_outputs = decoder_dense(decoder_outputs)


model = Model([encoder_inputs, decoder_inputs], decoder_outputs)

optimizer = RMSprop(lr=learning_rate, rho=0.9, epsilon=1e-08, decay=0.0, clipvalue = gradient_clip_value)
model.compile(optimizer = optimizer, loss='categorical_crossentropy')

model.fit_generator(generate_input_from_file('./dataset/image_embeddings_to_sentence/stories_to_index_train.hdf5',
                                             './dataset/vist2017_vocabulary.json', batch_size),
                    steps_per_epoch = num_samples / batch_size, epochs = epochs)

ts = time.time()
end_time = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')

model.save('./trained_models/' + str(start_time)+" - "+ str(end_time)+':image_to_text.h5')