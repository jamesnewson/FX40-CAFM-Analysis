import os
from PIL import Image
import numpy as np
from pspylib.tiff.reader import TiffReader
from pspylib.tiff.writer import Writer
from matplotlib.colors import LinearSegmentedColormap

class Read_tiff:
    def __call__(self,tiff_path):
        self.tiff = TiffReader(tiff_path)
        dict={}
        try:
            dict['HEADER'] = self.__dict_header()
        except:
            #print("No Data")
            return -1
        try:
            dict['SPECT_DATA'] = self.__spect_data_to_array()
            dict['SPECT_HEADER'] = self.__dict_spect_header()
            dict['SPECT_CH_INFO'] = self.__dict_spect_ch_info()
        except:
            #print("No spectroscopy data in this TIFF file.")
            x=1
        try:
            dict['IMAGE'] = self.__zdata_to_array()
            dict['THUMBNAIL'] = self.__thumbnail_to_array()
            dict['COLORMAP'] = self.__colormap_to_matplot()
        except:
            #print("No image data in this TIFF file.")
            x=1
            
        return dict, self.tiff
    
    @staticmethod
    def __cvt_uint16(value):
        word = ""
        for alphabet in value[0]:
            if alphabet != 0:
                word += chr(alphabet)
            else:
                pass
        return word

    def __thumbnail_to_array(self):
        thumb = self.tiff.data.metaData.thumbnail
        header = self.tiff.data.scanHeader.scanHeader
        dshape = (int(header['height'][0]), int(header['width'][0]))
        thumb_dshape = [0, 0]
        if (dshape[0] < 256) | (dshape[1] < 256):
            if dshape[0] > dshape[1]:
                thumb_dshape[0] = 256 
                thumb_dshape[1] = round(dshape[1] * 256 / dshape[0])
            if dshape[1] > dshape[0]:
                thumb_dshape[1] = 256 
                thumb_dshape[0] = round(dshape[0] * 256 / dshape[1])
        else: thumb_dshape = [256,256]
        return np.reshape(thumb,thumb_dshape)

    def __zdata_to_array(self):
        Zdata = self.tiff.data.scanData.ZData
        header = self.tiff.data.scanHeader.scanHeader
        dshape = (int(header['height'][0]), int(header['width'][0]))
        npy = np.reshape(Zdata,dshape)
        npy = np.flipud(npy)
        return npy

    def __colormap_to_matplot(self):
        ori_cm = self.tiff.data.metaData.colorMap['colorMap'][0]
        r = np.array(ori_cm)[:256]
        g = np.array(ori_cm)[256:512]
        b = np.array(ori_cm)[512:768]
        rgb_cm = np.dstack([r,g,b])[0] / 65536
        cmap_name = 'meta_cmap'
        meta_cmap = LinearSegmentedColormap.from_list(cmap_name, rgb_cm,N=128)
        return  meta_cmap

    def __dict_header(self):
        result_dict={}
        Header = self.tiff.data.scanHeader.scanHeader
        for i in Header.items():
            if i[-1][-1] == 'uint16':
                cvt_data = self.__cvt_uint16(i[-1])
                result_dict[i[0]] = cvt_data
            else:
                result_dict[i[0]] =i[-1][0]
        return result_dict
 
    def __dict_spect_header(self):
        result_dict = {}
        SpectHeader = self.tiff.data.spectHeader.spectHeader
        for i in SpectHeader.items():
            if[-1][-1] == 'uint16':
                cvt_data = self.__cvt_uint16(i[-1])
                result_dict[i[0]] = cvt_data
            else:
                result_dict[i[0]] = i[-1][0]
        return result_dict
 
    def __dict_spect_ch_info(self):
        result_dict = {}
        ChInfo = self.tiff.data.spectHeader.channelInfo
        for j in ChInfo.items():
            ch = 'ch'+str(j[0])
            result_dict[ch] ={}
            for i in j[1].items():
                if i[-1][-1] == 'uint16':
                    cvt_data = self.__cvt_uint16(i[-1])
                    result_dict[ch][i[0]] = cvt_data
                else:
                    result_dict[ch][i[0]] = i[-1][0]
        return result_dict
    
    def __spect_data_to_array(self):
        spect_data = np.array(self.tiff.data.spectData.rawData,dtype=np.float64)
        spect_ch_info = self.tiff.data.spectHeader.channelInfo
        number_of_ch = spect_data.shape[1]
        for i in range(number_of_ch):
            spect_data[:,i,:] *= float(spect_ch_info[i]['gain'][0])
        return spect_data    


class Write_tiff():
    def __call__(self, orig_tiff, dict_tiff, file_path):
        self.copy_tiff = orig_tiff
        self.dict_tiff = dict_tiff
        try:
            self.__copy_paste_image()
        except:
            print("No image data to write in this TIFF file.")
        
        # TODO: Need Debugging 
        # try:
        #     self.__copy_paste_spectroscopy()
        # except:
        #     print("No spectroscopy data to write in this TIFF file.")

        dir_path =os.path.dirname(file_path)
        if not os.path.exists(dir_path):os.makedirs(dir_path)
        Writer(data=self.copy_tiff.data, path=file_path)

    def __copy_paste_image(self):

        image = self.dict_tiff['IMAGE']
        self.dict_tiff['THUMBNAIL'] = self.__cvt_thumbnail(image)
        thumbnail  = self.dict_tiff['THUMBNAIL'].astype(int)
        self.copy_tiff.data.metaData.thumbnail = np.reshape(thumbnail.copy(), (-1,))
        z_array = np.flipud(self.dict_tiff['IMAGE'])
        self.copy_tiff.data.scanData.ZData = np.reshape(z_array.copy(), (-1,))

    def __copy_paste_spectroscopy(self):

        spect_ch_info = self.copy_tiff.data.spectHeader.channelInfo
        spect_array = self.dict_tiff['SPECT_DATA']
        number_of_ch = spect_array.shape[1]
        for i in range(number_of_ch):
            spect_array[:, i, :] /= float(spect_ch_info[i]['gain'][0])
        spect_data =  spect_array.copy().astype(self.copy_tiff.data.spectData.rawData.dtype)
        self.copy_tiff.data.spectData.rawData = spect_data
  
    
    def __cvt_thumbnail(self,npy):
        ori_shape = npy.shape
        norm_thumbnail = self.__minMax(npy) * 255
        norm_thumbnail = norm_thumbnail.astype(int)
        img = Image.fromarray(norm_thumbnail)

        if (ori_shape[0] < 256) | (ori_shape[1] < 256):
            if ori_shape[0] < ori_shape[1]:
                aspect_ratio = 256/ori_shape[1]
                resize_height = round(ori_shape[0] * aspect_ratio)
                thumbnail =  img.resize((256,resize_height),Image.NEAREST)
            else:
                aspect_ratio = 256/ori_shape[0]
                resize_width = round(ori_shape[1] * aspect_ratio)
                thumbnail = img.resize((resize_width,256),Image.NEAREST)
        else:
            thumbnail = img.resize((256,256),Image.NEAREST)
        thumbnail = np.array(thumbnail)
        return thumbnail 

    @staticmethod
    def __minMax(npy):
        # Min = 0, Max = 1
        min_npy = np.min(npy)
        denominator = (np.max(npy) - min_npy) + 1e-16
        return (npy - min_npy) / denominator