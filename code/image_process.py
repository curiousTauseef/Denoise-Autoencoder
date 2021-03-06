import os, shutil
import glob
from PIL import Image
import numpy as np
import cv2
from skimage import io as io2

class SplitImage:
    def __init__(self,network_config, train_config, test_config):
        self.network_config = network_config
        self.train_config = train_config
        self.test_config = test_config

    def clean_directory(self, folder):
        for filename in os.listdir(folder):
            file_path = os.path.join(folder, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                print('Failed to delete %s. Reason: %s' % (file_path, e))

    def raw_to_png(self, width, height):

        filelist = [f for f in glob.glob(self.test_config.pngdir + "**/*.raw", recursive=True)]
        self.clean_directory(self.test_config.noisy_pngoutdir)
        self.clean_directory(self.test_config.ir_pngoutdir)
        ir_count , noisy_count = 0, 0
        for f in filelist:
            outDir = self.test_config.noisy_pngoutdir
            img = np.fromfile(f, dtype='uint16', sep="")
            name, idx = "res-", noisy_count
            if "Infrared" in f:
                outDir = self.test_config.ir_pngoutdir
                img = np.fromfile(f, dtype='uint8', sep="")
                name, idx = "left-", ir_count
                ir_count += 1
            else:
                noisy_count += 1
            name = name + str(idx)
            outfile = outDir + '/' + name + self.test_config.IMAGE_EXTENSION
            img = img.reshape([height, width])
            if "Infrared" in f:
                img = img.astype('uint8')
            else:
                img = img.astype('uint16')
            cv2.imwrite(outfile, img)

    def normalize_images(self,img_path, height = 720, width = 1280):
        img = cv2.imread(img_path)
        normalizedImg = np.zeros((height, width))
        normalizedImg = cv2.normalize(img, normalizedImg, 70, 255, cv2.NORM_MINMAX)
        normalizedImg[np.where(img == 0)] = 0
        normalized_dir = r"./images/normalized"
        normalized_outfile = normalized_dir + '/'  + 'normalized-' + img_path.split('-')[1]
        cv2.imwrite(normalized_outfile, normalizedImg)

    def mask_pure_images(self, vars):
        pure_images_dir, noisy_images_dir, masked_pure = vars
        self.clean_directory(masked_pure)
        self.clean_directory(self.train_config.masked_noisy)
        purefilelist = [f for f in glob.glob(pure_images_dir + "**/*" + self.network_config.IMAGE_EXTENSION, recursive=True)]
        purefilelist.sort()
        noisyfilelist = [f for f in glob.glob(noisy_images_dir + "**/*" + self.network_config.IMAGE_EXTENSION, recursive=True)]
        noisyfilelist.sort()

        for i,f in enumerate(purefilelist):
            if f.endswith(self.network_config.IMAGE_EXTENSION):
                name = os.path.basename(f)
                name = os.path.splitext(name)[0]
                name_noisy = os.path.basename(noisyfilelist[i])
                name_noisy = os.path.splitext(name_noisy)[0]
                path = masked_pure + '/' + name + self.network_config.IMAGE_EXTENSION
                path_noisy = self.train_config.masked_noisy + '/' + name_noisy + self.network_config.IMAGE_EXTENSION

                pure_img = cv2.imread(purefilelist[i], cv2.IMREAD_UNCHANGED)
                noisy_img = cv2.imread(noisyfilelist[i], cv2.IMREAD_UNCHANGED)
                # Creating a Mask
                mask = np.zeros(pure_img.shape, np.uint8)
                mask[np.where(noisy_img == 0)] = 1
                #cv2.imshow('MASK', mask*255)

                kernel = np.ones((3, 3), np.uint8)
                erosion = cv2.erode(mask, kernel, iterations=self.network_config.EROSION_ITERATIONS)
                #dilation = cv2.dilate(erosion, kernel)
                #cv2.imshow('EROSION', erosion*255)
                #cv2.imshow('DILATION', dilation * 255)
                #pure_img[np.where(noisy_img == 0)] = 0 # old mask
                #cv2.imshow('PURE ', pure_img)
                #cv2.imshow('NOISY ', noisy_img)

                # Remove red background from pure and noisy
                if self.network_config.REMOVE_BACKGROUND :
                    max_val = np.max(pure_img)
                    noisy_img[np.where(pure_img == max_val)] = 0
                    pure_img[np.where(pure_img == max_val)] = 0
                    io2.imsave(path_noisy, noisy_img)
                #cv2.imshow('PURE', pure_img)
                #cv2.imshow('NOISY MASKED', noisy_img)

                # Apply mask on pure
                pure_img[np.where(erosion == 1)] = 0
                #cv2.imshow('PURE MASKED', pure_img)
                io2.imsave(path, pure_img)

    def get_split_img(self, config_list, cropped_w, cropped_h):

        for config in config_list:
            imgdir, savedir, is_ir = config

            self.clean_directory(savedir)
            filelist = [f for f in glob.glob(imgdir + "**/*" + self.network_config.IMAGE_EXTENSION, recursive=True)]
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
                        save_to= os.path.join(savedir, name +'_{:03}' +'_row_' + str(row_i) +'_col_' + str(col_i) +'_width' + str(w) +'_height' + str(h) + self.network_config.IMAGE_EXTENSION)
                        crop.save(save_to.format(frame_num))
                        frame_num += 1
                rolling_frame_num += frame_num


    def get_test_split_img(self, config_list):
        for config in config_list:
            filelist, total_cropped_images, cropped_images_dir, cropped_w, cropped_h, is_ir, origin_files_index_size_path = config
            for idx, file in enumerate(filelist):
                w, h = (cropped_w, cropped_h)
                rolling_frame_num = 0
                name = os.path.basename(file)
                name = os.path.splitext(name)[0]

                if not os.path.exists(cropped_images_dir + r'/' + name):
                    os.makedirs(cropped_images_dir + r'/' + name)
                    new_cropped_images_dir = cropped_images_dir + r'/' + name

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
                        save_to= os.path.join(new_cropped_images_dir, name +'_{:03}' +'_row_' + str(row_i) +'_col_' + str(col_i) +'_width' + str(w) +'_height' + str(h) + self.network_config.IMAGE_EXTENSION)
                        crop.save(save_to.format(frame_num))
                        frame_num += 1
                    origin_files_index_size_path[idx] =  (rolling_frame_num, width, height, file)

                total_cropped_images[idx] = frame_num

    def convert_16bit_to_8bit(file):
        image = cv2.imread(file, cv2.IMREAD_UNCHANGED)
        return image

    def image_to_array(self, iteration, images_num_to_process, vars, cropped_image_offsets=[]):
        cropped_w, cropped_h, cropped_images, ir_images, channels = vars
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

        images_plt = [cv2.imread(f, cv2.IMREAD_UNCHANGED) for f in im_files if f.endswith(self.network_config.IMAGE_EXTENSION)]
        ir_images_plt = [cv2.imread(f, cv2.IMREAD_UNCHANGED) for f in ir_im_files if f.endswith(self.network_config.IMAGE_EXTENSION)]

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

    def image_to_array_test(self, cropped_images, ir_images, cropped_image_offsets, vars ):
        cropped_w, cropped_h, channels = vars
        im_files = []
        ir_im_files = []
        for fname in os.listdir(cropped_images):
            path = os.path.join(cropped_images, fname)
            if os.path.isdir(path):
                # skip directories
                continue
            im_files.append(path)
        im_files.sort()

        if not self.network_config.TEST_REAL_DATA:
            for fname in os.listdir(ir_images):
                path = os.path.join(ir_images, fname)
                if os.path.isdir(path):
                    # skip directories
                    continue
                ir_im_files.append(path)
            ir_im_files.sort()

        if self.network_config.TEST_REAL_DATA:
            cropped_image_offsets.append([0,0])
            cropped_image_offsets.append([0, self.test_config.test_img_width])
        else:
            for i in range(len(im_files)):
                cropped_image_offsets.append([os.path.basename(im_files[i]).split('_')[3], os.path.basename(im_files[i]).split('_')[5]])

        images_plt = [cv2.imread(f, cv2.IMREAD_UNCHANGED) for f in im_files if f.endswith(self.network_config.IMAGE_EXTENSION)]
        ir_images_plt = [cv2.imread(f, cv2.IMREAD_UNCHANGED) for f in ir_im_files if f.endswith(self.network_config.IMAGE_EXTENSION)]

        images_plt = np.array(images_plt)
        ir_images_plt = np.array(ir_images_plt)
        images_plt = images_plt.reshape(images_plt.shape[0], cropped_w, cropped_h, 1)
        ir_images_plt = ir_images_plt.reshape(ir_images_plt.shape[0], cropped_w, cropped_h, 1)

        im_and_ir = images_plt
        if channels > 1:
            im_and_ir = np.stack((images_plt,ir_images_plt), axis=3)
            im_and_ir = im_and_ir.reshape(im_and_ir.shape[0], cropped_w, cropped_h, channels)

        img = np.array(im_and_ir)
        # Parse numbers as floats
        img = img.astype('float32')
        
        # Normalize data : remove average then devide by standard deviation
        img = (img - np.average(img)) / np.var(img)
        #img = img / 65535
        return img