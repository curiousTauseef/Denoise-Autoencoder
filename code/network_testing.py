import os, sys
import glob
import time
import numpy as np
from skimage import img_as_uint
import cv2
import keras

class NetworkTesting:
    def __init__(self, test_config, image_config):
        self.test_config = test_config
        self.image_config = image_config

    def test(self):
        old_stdout = sys.stdout
        model = keras.models.load_model(self.test_config.test_model_name)
        print('Testing model', str(self.test_config.test_model_name.split('.')[-1]), '..')
        name = self.test_config.logs_path + '/output_' + str(self.test_config.test_model_name.split('.')[-1]) + '.log'
        log_file = open(name, "w")
        sys.stdout = log_file
        print('prediction time : ')

        if self.test_config.TEST_REAL_DATA:
            self.test_config.imgdir = self.test_config.realDataDir

        # clean directories before processing
        self.image_config.clean_directory(self.test_config.cropped_images)
        self.image_config.clean_directory(self.test_config.ir_cropped_images)
        self.image_config.clean_directory(self.test_config.denoised_dir)

        filelist = [f for f in glob.glob(self.test_config.imgdir + "**/*" + self.test_config.IMAGE_EXTENSION, recursive=True)]
        ir_filelist = [f for f in glob.glob(self.test_config.ir_imgdir + "**/*" + self.test_config.IMAGE_EXTENSION, recursive=True)]
        total_cropped_images = [0]*len(filelist)
        ir_total_cropped_images = [0]*len(ir_filelist)

        ir_config = (ir_filelist, ir_total_cropped_images, self.image_config.ir_cropped_images, self.image_config.test_img_width, self.image_config.test_img_height, True, {})
        noisy_config = (filelist, total_cropped_images, self.image_config.cropped_images, self.image_config.test_img_width, self.image_config.test_img_height, False, self.image_config.origin_files_index_size_path_test)

        config_list = [ir_config, noisy_config]
        self.image_config.get_test_split_img(config_list)

        dirs_list = [self.test_config.cropped_images + '/' + dir_ for dir_ in os.listdir(self.test_config.cropped_images)]

        for i,directory in enumerate(dirs_list):

            cropped_image_offsets = []
            ir_cropped_images_file = self.test_config.ir_cropped_images + r'/' + 'left-' + str(directory.split('-')[-1])
            #test_img_width, test_img_height, channels = self.test_config.get_image_to_array_test_input()
            samples = self.image_config.image_to_array_test(directory, ir_cropped_images_file, cropped_image_offsets,
                                                            self.test_config.get_image_to_array_test_input())
            rolling_frame_num, width, height, origin_file_name = self.test_config.origin_files_index_size_path_test[i]
            cropped_w, cropped_h = self.test_config.test_img_width, self.test_config.test_img_height
            whole_image = np.zeros((height, width, self.test_config.channels), dtype="float32")

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
            outfile = self.test_config.denoised_dir + '/' + denoised_name.split('-')[0] + '' + '_denoised-' + denoised_name.split('-')[1] + self.test_config.IMAGE_EXTENSION
            whole_image = img_as_uint(whole_image)
            cv2.imwrite(outfile, whole_image[:,:,0])
        sys.stdout = old_stdout
        log_file.close()