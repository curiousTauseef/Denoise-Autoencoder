import os, sys, shutil
import keras
import time
import tensorflow as tf
from keras import backend as kb
from keras.models import *
from keras.layers import *
from keras.optimizers import *
from keras.callbacks import ModelCheckpoint
import glob
from PIL import Image
import numpy as np
import cv2
from skimage import io as io2
from skimage import img_as_uint


#============================================ M A I N =================================================
root = r"C:\Users\user\Documents\test_unet_flow"
images_path = root + r"\images"
models_path = root  + r"\models"
logs_path = root  + r"\logs"
imgdir_pure = images_path + r"\train\pure"
imgdir_noisy = images_path + r"\train\noisy"
imgdir_ir = images_path + r"\train\ir"
savedir_pure = images_path + r"\cropped_images\pure"
savedir_noisy = images_path + r"\cropped_images\noisy"
cropped_train_images_ir = images_path + r"\cropped_images\ir"
cropped_train_images_pure = images_path + r".\cropped_images\pure"
cropped_train_images_noisy = images_path + r"\cropped_images\noisy"

paths = [images_path, models_path, logs_path, imgdir_pure, imgdir_noisy, imgdir_ir, savedir_pure, savedir_noisy,
              cropped_train_images_ir, cropped_train_images_pure, cropped_train_images_noisy]

for path in paths:
    if not os.path.exists(path):
        os.makedirs(path)

#======================================================================================================
IMAGE_EXTENSION = '.png'

def image_to_array(iteration, images_num_to_process, cropped_w, cropped_h, cropped_images, ir_images, channels, cropped_image_offsets=[]):
    im_files, ir_im_files  = [], []
    ls = os.listdir(cropped_images)
    ls.sort()
    limit = iteration+images_num_to_process
    if iteration+images_num_to_process > len(ls):
        limit = len(ls)

    for i in range(iteration, limit):
        path = os.path.join(cropped_images, ls[i])
        if os.path.isdir(path):
            # skip directories
            continue
        im_files.append(path)
    ls = os.listdir(ir_images)
    ls.sort()
    for i in range(iteration, limit):
        path = os.path.join(ir_images, ls[i])
        if os.path.isdir(path):
            # skip directories
            continue
        ir_im_files.append(path)

    im_files.sort()
    ir_im_files.sort()
    for i in range(len(im_files)):
        cropped_image_offsets.append([im_files[i].split('_')[4], im_files[i].split('_')[6]])

    images_plt = [cv2.imread(f, cv2.IMREAD_UNCHANGED) for f in im_files if f.endswith(IMAGE_EXTENSION)]
    ir_images_plt = [cv2.imread(f, cv2.IMREAD_UNCHANGED) for f in ir_im_files if f.endswith(IMAGE_EXTENSION)]

    images_plt = np.array(images_plt)
    ir_images_plt = np.array(ir_images_plt)
    images_plt = images_plt.reshape(images_plt.shape[0], cropped_w, cropped_h, 1)
    ir_images_plt = ir_images_plt.reshape(ir_images_plt.shape[0], cropped_w, cropped_h, 1)

    im_and_ir = images_plt
    if channels > 1:
        im_and_ir = np.stack((images_plt,ir_images_plt), axis=3)
        im_and_ir = im_and_ir.reshape(im_and_ir.shape[0], cropped_w, cropped_h, channels)

    # convert your lists into a numpy array of size (N, H, W, C)
    img = np.array(im_and_ir)
    # Parse numbers as floats
    img = img.astype('float32')

    # Normalize data : remove average then devide by standard deviation
    img = (img - np.average(img)) / np.var(img)
    #img = img / 65535
    return img

#============================================ T R A I N ===============================================
# other configuration
channels = 2
img_width, img_height = 128, 128

#Unet
unet_steps_per_epoch = 1700
unet_epochs = 1

# Get the file paths
kb.clear_session()
gpus = tf.config.experimental.list_physical_devices('GPU')
print("Num GPUs Available: ", len(tf.config.experimental.list_physical_devices('GPU')))
if gpus:
    try:
        # Currently, memory growth needs to be the same across GPUs
        for gpu in gpus:
            tf.config.experimental.set_memory_growth(gpu, True)
        logical_gpus = tf.config.experimental.list_logical_devices('GPU')
        print(len(gpus), "Physical GPUs,", len(logical_gpus), "Logical GPUs")
    except RuntimeError as e:
        # Memory growth must be set before GPUs have been initialized
        print(e)

print('Starting a training process ..')
print('Preparing training data for CNN ..')
# save output to logs
old_stdout = sys.stdout
timestr = time.strftime("%Y%m%d-%H%M%S")
model_name = 'DEPTH_' + timestr + '.model'
name = logs_path + r'/loss_output_' + model_name + '.log'
log_file = open(name, "w")
sys.stdout = log_file
print('Loss function output of model :', model_name, '..')

######## Create a Unet model and compile
input_size = (img_width, img_height, channels)
inputs = Input(input_size)
conv1 = Conv2D(64, 3, activation='relu', padding='same', kernel_initializer='he_normal')(inputs)
conv1 = Conv2D(64, 3, activation='relu', padding='same', kernel_initializer='he_normal')(conv1)
pool1 = MaxPooling2D(pool_size=(2, 2))(conv1)
conv2 = Conv2D(128, 3, activation='relu', padding='same', kernel_initializer='he_normal')(pool1)
conv2 = Conv2D(128, 3, activation='relu', padding='same', kernel_initializer='he_normal')(conv2)
pool2 = MaxPooling2D(pool_size=(2, 2))(conv2)
conv3 = Conv2D(256, 3, activation='relu', padding='same', kernel_initializer='he_normal')(pool2)
conv3 = Conv2D(256, 3, activation='relu', padding='same', kernel_initializer='he_normal')(conv3)
pool3 = MaxPooling2D(pool_size=(2, 2))(conv3)
conv4 = Conv2D(512, 3, activation='relu', padding='same', kernel_initializer='he_normal')(pool3)
conv4 = Conv2D(512, 3, activation='relu', padding='same', kernel_initializer='he_normal')(conv4)
drop4 = Dropout(0.5)(conv4)
pool4 = MaxPooling2D(pool_size=(2, 2))(drop4)

conv5 = Conv2D(1024, 3, activation='relu', padding='same', kernel_initializer='he_normal')(pool4)
conv5 = Conv2D(1024, 3, activation='relu', padding='same', kernel_initializer='he_normal')(conv5)
drop5 = Dropout(0.5)(conv5)

up6 = Conv2D(512, 2, activation='relu', padding='same', kernel_initializer='he_normal')(UpSampling2D(size=(2, 2))(drop5))
merge6 = concatenate([drop4, up6], axis=3)
conv6 = Conv2D(512, 3, activation='relu', padding='same', kernel_initializer='he_normal')(merge6)
conv6 = Conv2D(512, 3, activation='relu', padding='same', kernel_initializer='he_normal')(conv6)

up7 = Conv2D(256, 2, activation='relu', padding='same', kernel_initializer='he_normal')(UpSampling2D(size=(2, 2))(conv6))
merge7 = concatenate([conv3, up7], axis=3)
conv7 = Conv2D(256, 3, activation='relu', padding='same', kernel_initializer='he_normal')(merge7)
conv7 = Conv2D(256, 3, activation='relu', padding='same', kernel_initializer='he_normal')(conv7)

up8 = Conv2D(128, 2, activation='relu', padding='same', kernel_initializer='he_normal')(
    UpSampling2D(size=(2, 2))(conv7))
merge8 = concatenate([conv2, up8], axis=3)
conv8 = Conv2D(128, 3, activation='relu', padding='same', kernel_initializer='he_normal')(merge8)
conv8 = Conv2D(128, 3, activation='relu', padding='same', kernel_initializer='he_normal')(conv8)

up9 = Conv2D(64, 2, activation='relu', padding='same', kernel_initializer='he_normal')(UpSampling2D(size=(2, 2))(conv8))
merge9 = concatenate([conv1, up9], axis=3)
conv9 = Conv2D(64, 3, activation='relu', padding='same', kernel_initializer='he_normal')(merge9)
conv9 = Conv2D(64, 3, activation='relu', padding='same', kernel_initializer='he_normal')(conv9)
conv9 = Conv2D(2, 3, activation='relu', padding='same', kernel_initializer='he_normal')(conv9)
conv10 = Conv2D(channels, 1, activation='sigmoid')(conv9)

model = Model(inputs=inputs, outputs=conv10)

model.compile(optimizer=Adam(lr=1e-4), loss='binary_crossentropy', metrics=['accuracy'])

model.summary()
compiled_model = model
######## Model is compiled

print('Cropping training data ..')
cropped_w, cropped_h = img_width, img_height
config_list = [(imgdir_ir, cropped_train_images_ir, True), (imgdir_pure, savedir_pure, False),
               (imgdir_noisy, savedir_noisy, False)]
for config in config_list:
    imgdir, savedir, is_ir = config
    for filename in os.listdir(savedir):
        file_path = os.path.join(savedir, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print('Failed to delete %s. Reason: %s' % (file_path, e))

    filelist = [f for f in glob.glob(imgdir + "**/*" + IMAGE_EXTENSION, recursive=True)]
    w, h = (cropped_w, cropped_h)
    rolling_frame_num = 0
    for i, file in enumerate(filelist):
        name = os.path.basename(file)
        name = os.path.splitext(name)[0]

        if is_ir:
            ii = cv2.imread(file)
            gray_image = cv2.cvtColor(ii, cv2.COLOR_BGR2GRAY)
            img = Image.fromarray(np.array(gray_image).astype("uint16"))
        else:
            img = Image.fromarray(np.array(Image.open(file)).astype("uint16"))

        width, height = img.size
        frame_num = 0
        for col_i in range(0, width, w):
            for row_i in range(0, height, h):
                crop = img.crop((col_i, row_i, col_i + w, row_i + h))
                save_to = os.path.join(savedir,
                                       name + '_{:03}' + '_row_' + str(row_i) + '_col_' + str(col_i) + '_width' + str(
                                           w) + '_height' + str(h) + IMAGE_EXTENSION)
                crop.save(save_to.format(frame_num))
                frame_num += 1
        rolling_frame_num += frame_num

##### all data is cropped

save_model_name = models_path +'/' + model_name
images_num_to_process = 1000
all_cropped_num = len(os.listdir(cropped_train_images_pure))
iterations = all_cropped_num // images_num_to_process
if all_cropped_num % images_num_to_process > 0 :
    iterations += 1
for i in range(iterations):
    print('*************** Iteration : ', i, '****************')
    first_image = i*images_num_to_process
    if i == iterations-1:
        images_num_to_process = all_cropped_num - i*images_num_to_process
    pure_input_train = image_to_array(first_image , images_num_to_process, img_width, img_height, cropped_train_images_pure, cropped_train_images_ir, channels)
    noisy_input_train = image_to_array(first_image, images_num_to_process, img_width, img_height, cropped_train_images_noisy, cropped_train_images_ir, channels)

    # Start training Unet network
    model_checkpoint = ModelCheckpoint(models_path + r"\unet_membrane.hdf5", monitor='loss', verbose=1, save_best_only=True)
    compiled_model.fit(noisy_input_train, pure_input_train, steps_per_epoch=unet_steps_per_epoch, epochs=unet_epochs, callbacks=[model_checkpoint])

    # save the model
    compiled_model.save(save_model_name)
    compiled_model = keras.models.load_model(save_model_name)

sys.stdout = old_stdout
log_file.close()

#============================================ T E S T =================================================

origin_files_index_size_path_test = {}
test_img_width, test_img_height = 480, 480
img_width, img_height = test_img_width, test_img_height
#test_model_name = save_model_name
test_model_name = r"C:\Users\user\Documents\ML\models\DEPTH_20200903-132536.model_new"

imgdir = images_path + r"\tests\depth"
realDataDir = images_path + r"\real_scenes_png"
ir_imgdir = images_path + r"\tests\ir"
denoised_dir = images_path + r"\denoised"
cropped_images = images_path + r"\cropped_tests\depth"
ir_cropped_images = images_path + r"\cropped_tests\ir"
normalized_dir = images_path + r"\normalized"

pngdir = images_path + r"\real_data"
noisy_pngoutdir = images_path + r"\tests\depth"
ir_pngoutdir = images_path + r"\tests\ir"

paths = [imgdir, realDataDir, ir_imgdir, denoised_dir, cropped_images, ir_cropped_images,
         denoised_dir, normalized_dir, pngdir, noisy_pngoutdir, ir_pngoutdir]
for path in paths:
    if not os.path.exists(path):
        os.makedirs(path)

#================================= S T A R T   T E S T I N G ==========================================
old_stdout = sys.stdout
try:
    model = keras.models.load_model(test_model_name)
except Exception as e:
    print('Failed to load model %s. Reason: %s' % (test_model_name, e))


print('Testing model', str(test_model_name.split('.')[-1]), '..')
name = logs_path + '/output_' + str(test_model_name.split('.')[-1]) + '.log'
log_file = open(name, "w")
sys.stdout = log_file
print('prediction time : ')

# clean directories before processing
folders = [cropped_images, ir_cropped_images, denoised_dir]
for folder in folders:
    for filename in os.listdir(folder):
        file_path = os.path.join(folder, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print('Failed to delete %s. Reason: %s' % (file_path, e))

filelist = [f for f in glob.glob(imgdir + "**/*" + IMAGE_EXTENSION, recursive=True)]
ir_filelist = [f for f in glob.glob(ir_imgdir + "**/*" + IMAGE_EXTENSION, recursive=True)]
total_cropped_images = [0]*len(filelist)
ir_total_cropped_images = [0]*len(ir_filelist)

########### SPLIT IMAGES ##################
ir_config = (ir_filelist, ir_total_cropped_images, ir_cropped_images, test_img_width, test_img_height, True, {})
noisy_config = (filelist, total_cropped_images, cropped_images, test_img_width, test_img_height, False, origin_files_index_size_path_test)
config_list = [ir_config, noisy_config]

for config in config_list:
    filelist, total_cropped_images, cropped_images_dir, cropped_w, cropped_h, is_ir, origin_files_index_size_path = list(config)
    for idx, file in enumerate(filelist):
        w, h = (cropped_w, cropped_h)
        rolling_frame_num = 0
        name = os.path.basename(file)
        name = os.path.splitext(name)[0]

        if not os.path.exists(cropped_images_dir + r'/' + name):
            os.makedirs(cropped_images_dir + r'/' + name)
            new_cropped_images_dir = cropped_images_dir + r'/' + name

        if is_ir:
            # ir images has 3 similar channels, we need only 1 channel
            ii = cv2.imread(file)
            gray_image = cv2.cvtColor(ii, cv2.COLOR_BGR2GRAY)
            img = Image.fromarray(np.array(gray_image).astype("uint16"))
            #img = np.array(gray_image).astype("uint16")
        else:
            img = Image.fromarray(np.array(Image.open(file)).astype("uint16"))
            #img = np.array(Image.open(file)).astype("uint16")
            #cv2.imwrite(r"C:\Users\user\Documents\test_unet_flow\images\im"+str(idx)+".png", img)

        width, height = 848, 480 #img.size
        frame_num = 0
        for col_i in range(0, width, w):
            for row_i in range(0, height, h):
                crop = img.crop((col_i, row_i, col_i + w, row_i + h))
                #crop = img[row_i:row_i+h, col_i:col_i+w]
                #crop[0][0] = 255
                save_to = os.path.join(new_cropped_images_dir, name + '_{:03}' + '_row_' + str(row_i) + '_col_' + str(col_i) + '_width' + str(w) + '_height' + str(h) + IMAGE_EXTENSION)
                crop.save(save_to.format(frame_num))
                #cv2.imwrite(save_to.format(frame_num), crop)
                frame_num += 1
            origin_files_index_size_path[idx] = (rolling_frame_num, width, height, file)

        total_cropped_images[idx] = frame_num

dirs_list = [cropped_images + '/' + dir_ for dir_ in os.listdir(cropped_images)]

########### IMAGE TO ARRAY  ##################
for i,directory in enumerate(dirs_list):

    cropped_image_offsets = []
    ir_cropped_images_file = ir_cropped_images + r'/' + 'left-' + str(directory.split('-')[-1])

    cropped_w, cropped_h = test_img_width, test_img_height
    im_files = []
    ir_im_files = []
    for fname in os.listdir(directory):
        path = os.path.join(directory, fname)
        if os.path.isdir(path):
            # skip directories
            continue
        im_files.append(path)
    im_files.sort()

    for fname in os.listdir(ir_cropped_images_file):
        path = os.path.join(ir_cropped_images_file, fname)
        if os.path.isdir(path):
            # skip directories
            continue
        ir_im_files.append(path)
    ir_im_files.sort()

    for i in range(len(im_files)):
        cropped_image_offsets.append([os.path.basename(im_files[i]).split('_')[3], os.path.basename(im_files[i]).split('_')[5]])

    images_plt = [cv2.imread(f, cv2.IMREAD_UNCHANGED) for f in im_files if
                  f.endswith(IMAGE_EXTENSION)]
    ir_images_plt = [cv2.imread(f, cv2.IMREAD_UNCHANGED) for f in ir_im_files if
                     f.endswith(IMAGE_EXTENSION)]

    images_plt = np.array(images_plt)
    ir_images_plt = np.array(ir_images_plt)
    images_plt = images_plt.reshape(images_plt.shape[0], cropped_w, cropped_h, 1)
    ir_images_plt = ir_images_plt.reshape(ir_images_plt.shape[0], cropped_w, cropped_h, 1)

    im_and_ir = images_plt
    if channels > 1:
        im_and_ir = np.stack((images_plt, ir_images_plt), axis=3)
        im_and_ir = im_and_ir.reshape(im_and_ir.shape[0], cropped_w, cropped_h, channels)

    img = np.array(im_and_ir)
    # Parse numbers as floats
    img = img.astype('float32')

    # Normalize data : remove average then devide by standard deviation
    #img = (img - np.average(img)) / np.var(img)
    #img = img / 65535
    img = img / 56535
    samples = img

    ###################################

    rolling_frame_num, width, height, origin_file_name = origin_files_index_size_path_test[i]
    cropped_w, cropped_h = test_img_width, test_img_height
    whole_image = np.zeros((height, width, channels), dtype="float32")

    t1 = time.perf_counter()
    for i in range(total_cropped_images[i]):
        # testing
        sample = samples[i:i+1]
        row, col = cropped_image_offsets[i]
        row, col = int(row), int(col)
        denoised_image = model.predict(sample)
        row_end = row + cropped_h
        col_end = col + cropped_w
        denoised_row = cropped_h
        denoised_col = cropped_w
        if row + cropped_h >= height:
            row_end = height-1
            denoised_row = abs(row-row_end)
        if col + cropped_w >= width:
            col_end = width-1
            denoised_col = abs(col - col_end)
        # combine tested images
        whole_image[row:row_end, col:col_end]=  denoised_image[:, 0:denoised_row,0:denoised_col, :]
    t2 = time.perf_counter()
    print('test: ', directory.split('/')[-1], ': ', t2 - t1, 'seconds')
    denoised_name = directory.split('/')[-1]
    outfile = denoised_dir + '/' + denoised_name.split('-')[0] + '' + '_denoised-' + denoised_name.split('-')[1] + IMAGE_EXTENSION
    whole_image = img_as_uint(whole_image)
    cv2.imwrite(outfile, whole_image[:,:,0])
sys.stdout = old_stdout
log_file.close()