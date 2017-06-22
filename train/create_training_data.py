import numpy as np
import json
import os
import ast
import random

from keras.applications import imagenet_utils
from keras.applications.inception_v3 import preprocess_input as preprocess_xception
from keras.preprocessing.image import load_img, img_to_array

# dimension: (height, width) of image
# train_split: fraction of data to use for training
# take_all: take all screenshot for a game or only one
# target: what to classify
# preprocess: basic or xception
def create_training_data(dimension=(240, 320), train_split=0.8, take_all=False, target='genre', preprocess_method='none'):

    # base paths
    data_dir = 'raw_data'
    output_dir = 'training_data'

    # preprocess functions
    if preprocess_method == 'vgg':
        preprocess = imagenet_utils.preprocess_input
    elif preprocess_method == 'xception':
        preprocess = preprocess_xception
    elif preprocess_method == 'none':
        preprocess = lambda x: x
    elif preprocess_method == 'mean_image':
        # preprocess later
        preprocess = lambda x: x
    elif preprocess_method == 'mean_pixel':
        # preprocess later
        preprocess = lambda x: x
    else:
        raise ValueError('invalid preprocess option ' + preprocess)

    # map of genres to indices and indices to genres
    index_to_genre = []
    genre_to_index = dict()

    # training and test data
    train_X = []
    train_Y = []
    test_X = []
    test_Y = []

    # if take_all = False: get extra screens from known games as additional test data
    extra_X = []
    extra_Y = []

    counter = 0
    total_count = len(os.listdir(data_dir))
    collect_training = True

    # iterate over game folders, randomly permuted
    folders = os.listdir(data_dir)[:10]
    random.shuffle(folders)
    for folder in folders:
        counter += 1
        if counter > train_split * total_count:
            collect_training = False
        appid = folder
        screen_dir = os.path.join(data_dir, appid)
        if not os.path.isdir(screen_dir):
            continue
        target_file = os.path.join(screen_dir, 'info.json')
        screen_files = []
        extra_file = None
        suffix = '.jpg'
        if take_all:
            for filename in os.listdir(screen_dir):
                if filename.endswith(suffix):
                    screen_files.append(os.path.join(screen_dir, filename))
        else:
            # find screen with highest number (least likely to be menu/title)
            priorities = list(range(0,5))
            found = False
            while (not found) and (not priorities == []):
                screen_name = str(priorities.pop()) + suffix
                if screen_name in os.listdir(screen_dir):
                    found = True
                    screen_files.append(os.path.join(screen_dir, screen_name))
                    if collect_training and (not screen_name.startswith('0')):
                        # get extra screen
                        extra_screen_name = str(priorities.pop()) + suffix
                        extra_file = os.path.join(screen_dir, extra_screen_name)

        # sanity check: if we found no screen, let's skip
        if screen_files == []:
            continue
        # read meta data
        target_id = -1
        with open(target_file, 'r') as game_info_file:
            game_info = game_info_file.read()
            jo = ast.literal_eval(game_info)
            # extract target
            if target == 'genre':
                try:
                    genre_strings = extract_genre(jo)
                # no genre info: next one
                except KeyError:
                    continue
                for genre_string in genre_strings:
                    if not genre_string in index_to_genre:
                        index_to_genre.append(genre_string)
                        genre_to_index[genre_string] = len(index_to_genre) - 1
                target_id = [genre_to_index[genre_string] for genre_string in genre_strings]
            else:
                raise ValueError('unknown target ' + target)

        # add to training/test data
        for screen_file in screen_files:
            screenshot = process_screen(screen_file, dimension, preprocess)
            if collect_training:
                train_X.append(screenshot)
                train_Y.append(target_id)
            else:
                test_X.append(screenshot)
                test_Y.append(target_id)
        if not extra_file == None:
            extra_screen = process_screen(extra_file, dimension, preprocess)
            extra_X.append(extra_screen)
            extra_Y.append(target_id)

    # transform genre lists to binary vector
    number_of_genres = len(index_to_genre)
    train_Y = transform_to_binary_matrix(train_Y, number_of_genres)
    test_Y = transform_to_binary_matrix(test_Y, number_of_genres)
    extra_Y = transform_to_binary_matrix(extra_Y, number_of_genres)

    # turn everything into proper numpy arrays
    train_X = np.asarray(train_X, dtype='uint8')
    test_X = np.asarray(test_X, dtype='uint8')
    train_Y = np.asarray(train_Y, dtype='int8')
    test_Y = np.asarray(test_Y, dtype='int8')

    if not extra_X == []:
        extra_X = np.asarray(extra_X, dtype='uint8')
        extra_Y = np.asarray(extra_Y, dtype='int8')

    # get mean for mean subtraction (done later to keep data files small)
    if preprocess_method == 'mean_image':
        preprocess_means = np.mean(train_X, axis=0)
        print(preprocess_means)

    elif preprocess_method == 'mean_pixel':
        preprocess_means = np.mean(train_X, axis=(0,1,2))
        print(preprocess_means)

    # dump everything into files

    # genres
    genre_file_path = os.path.join(output_dir, 'genres.txt')
    with open(genre_file_path, 'w') as genre_file:
        [genre_file.write(genre + os.linesep) for genre in index_to_genre]

    # preprocess type
    preprocess_path = os.path.join(output_dir, 'preprocess.txt')
    with open(preprocess_path, 'w') as preprocess_file:
        data = dict()
        data['preprocess'] = preprocess_method
        if preprocess_method in ['mean_pixel', 'mean_image']:
            means_path = os.path.join(output_dir, 'means.npy')
            np.save(means_path, preprocess_means)
        preprocess_file.write(str(data))

    # training/test data
    train_X_path = os.path.join(output_dir, 'train_X.npy')
    train_Y_path = os.path.join(output_dir, 'train_Y.npy')
    test_X_path = os.path.join(output_dir, 'test_X.npy')
    test_Y_path = os.path.join(output_dir, 'test_Y.npy')
    np.save(train_X_path, train_X)
    np.save(train_Y_path, train_Y)
    np.save(test_X_path, test_X)
    np.save(test_Y_path, test_Y)

    # extra data
    if not extra_X == []:
        extra_X_path = os.path.join(output_dir, 'extra_X.npy')
        extra_Y_path = os.path.join(output_dir, 'extra_Y.npy')
        np.save(extra_X_path, extra_X)
        np.save(extra_Y_path, extra_Y)

    # print some info
    print(str(number_of_genres) + ' genres found.')
    for genre in genre_to_index:
        index = genre_to_index[genre]
        train_count = len([i for i in train_Y if i[index] == 1])
        test_count = len([i for i in test_Y if i[index] == 1])
        print(genre + ' ' + str(train_count) + ' ' + str(test_count))

def extract_genre(jo):
    # filter out these 2 genres as they only appear once
    filtered_genres = ['Abenteuer', 'Web Publishing']
    genre_list = [genre['description'] for genre in jo['genres']
                    if not genre['description'] in filtered_genres]
    return genre_list

def transform_to_binary_matrix(data, count):
    for row in range(0, len(data)):
        ids = data[row]
        data[row] = np.asarray([1 if i in ids else -1 for i in range(0, count)], dtype='int8')
    return data

def process_screen(screen_file, dimension, preprocess):
    screenshot = load_img(screen_file, target_size=dimension)
    screenshot = img_to_array(screenshot)
    screenshot = np.expand_dims(screenshot, axis=0)
    screenshot = preprocess(screenshot)
    screenshot = screenshot[0]
    return screenshot

create_training_data(preprocess_method='mean_image', dimension=(240, 320))