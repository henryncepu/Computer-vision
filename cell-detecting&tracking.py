import matplotlib.pyplot as plt
import cv2
import numpy as np
import os
from collections import defaultdict
import math

class Obj:
    def __init__(self, path, previous_img):
        self.original_img = cv2.imread(path, 0)
        self.index = 0
        self.prev = previous_img
        self.next = None
        self.split_list = []
        self.split_new = []
        if previous_img is not None:
            previous_img.next = self
        self.normalize_img = None
        self.thresh = None
        self.contours = self.pre_processing()
        self.get_valid_contours()
        self.identify_cell = defaultdict(dict)
        self.register(previous_img)

    def get_valid_contours(self):
        valid_contours = []
        for c in self.contours:
            (x, y), radius = cv2.minEnclosingCircle(c)
            left_up = (x - radius, y + radius)
            right_down = (x + radius, y - radius)
            valid_contours.append((c, left_up, right_down))
        self.contours = []
        for i in range(len(valid_contours)):
            valid = True
            c = valid_contours[i]
            for j in range(len(valid_contours)):
                if i != j:
                    cv = valid_contours[j]
                    if c[1][0] >= cv[1][0] and c[1][1] <= cv[1][1] and \
                            c[2][0] <= cv[2][0] and c[2][1] >= cv[2][1]:
                        valid = False
                        break
            if valid:
                self.contours.append(c[0])

    def register(self, previous_img):
        if previous_img is None:
            self.register_initial()
        else:
            self.register_extend(previous_img)

    def register_initial(self):
        for c in self.contours:
            (x, y), radius = cv2.minEnclosingCircle(c)
            x = int(x)
            y = int(y)
            self.identify_cell[self.index]['radius'] = radius
            self.identify_cell[self.index]['center'] = (x, y)
            self.identify_cell[self.index]['area'] = cv2.contourArea(c)
            self.index += 1

    def register_extend(self, previous_img):
        self.index = previous_img.index
        new_index = set()
        for c in self.contours:
            (x, y), radius = cv2.minEnclosingCircle(c)
            x = int(x)
            y = int(y)
            area = cv2.contourArea(c)
            temp = []
            for key, value in previous_img.identify_cell.items():
                diff = pow((x - value['center'][0]), 2) + pow((y - value['center'][1]), 2)
                if diff < 2500:
                    temp.append((key, diff))
            if len(temp) > 0:
                temp = sorted(temp, key=lambda k: k[1], reverse=True)
                self.match(temp, radius, (x, y), area, new_index)
            else:
                new_index.add((radius, (x, y), area))
        for tup in new_index:
            if not self.find_split(tup):
                self.add_cell(self.index, tup[0], tup[1], tup[2])
                self.index += 1

    def find_split(self, test_point):
        center = test_point[1]
        temp = []
        for index, info in self.identify_cell.items():
            if index in self.prev.identify_cell:
                center_t = info['center']
                mid = ((center[0] + center_t[0]) / 2, (center[1] + center_t[1]) / 2)
                diff = self.distance(mid, self.prev.identify_cell[index]['center'])
                if diff < pow(self.prev.identify_cell[index]['radius'], 2):
                    temp.append((index, diff))
        if len(temp) > 0:
            temp = sorted(temp, key=lambda t: t[1])
            self.add_cell(self.index, test_point[0], test_point[1], test_point[2])
            self.add_cell(self.index + 1, self.identify_cell[temp[0][0]]['radius'],
                          self.identify_cell[temp[0][0]]['center'], self.identify_cell[temp[0][0]]['area'])
            self.identify_cell.pop(temp[0][0])
            self.prev.split_list.append(temp[0][0])
            self.split_new.append(self.index)
            self.split_new.append(self.index+1)
            self.index += 2
            return True
        else:
            return False

    def match(self, temp, radius, center, area, new_index):
        matched = False
        while len(temp) > 0:
            t = temp[-1]
            if t[0] not in self.identify_cell:
                self.add_cell(t[0], radius, center, area)
                self.identify_cell[t[0]]['diff'] = temp
                matched = True
                break
            else:
                if self.identify_cell[t[0]]['diff'][-1][1] > t[1]:
                    self.identify_cell[t[0]]['diff'].pop()
                    diff_replaced = self.identify_cell[t[0]]['diff']
                    radius_replaced = self.identify_cell[t[0]]['radius']
                    center_replaced = self.identify_cell[t[0]]['center']
                    area_replaced = self.identify_cell[t[0]]['area']
                    self.add_cell(t[0], radius, center, area)
                    self.identify_cell[t[0]]['diff'] = temp
                    self.match(diff_replaced, radius_replaced, center_replaced, area_replaced, new_index)
                    matched = True
                    break
            temp.pop()
        if not matched:
            new_index.add((radius, center, area))

    @staticmethod
    def distance(point1, point2):
        return pow(point1[0] - point2[0], 2) + pow(point1[1] - point2[1], 2)

    def get_rgb(self):
        result = np.zeros((self.thresh.shape[0], self.thresh.shape[1], 3))
        for i in range(len(self.thresh)):
            for j in range(len(self.thresh[i])):
                if self.thresh[i][j] != 0:
                    result[i][j] += np.array([255, 255, 255])
        return result.astype('uint8')

    def add_cell(self, c_index, radius, center, area):
        self.identify_cell[c_index]['radius'] = radius
        self.identify_cell[c_index]['center'] = center
        self.identify_cell[c_index]['area'] = area

    def draw_split_cell(self):
        img = self.get_rgb()
        for i in self.split_list:
            cv2.rectangle(img,
                          (int(self.identify_cell[i]['center'][0] - self.identify_cell[i]['radius']),
                           int(self.identify_cell[i]['center'][1] + self.identify_cell[i]['radius'])),
                          (int(self.identify_cell[i]['center'][0] + self.identify_cell[i]['radius']),
                           int(self.identify_cell[i]['center'][1] - self.identify_cell[i]['radius'])),
                          (255, 0, 0), 2)
        for i in self.split_new:
            cv2.rectangle(img,
                          (int(self.identify_cell[i]['center'][0] - self.identify_cell[i]['radius']),
                           int(self.identify_cell[i]['center'][1] + self.identify_cell[i]['radius'])),
                          (int(self.identify_cell[i]['center'][0] + self.identify_cell[i]['radius']),
                           int(self.identify_cell[i]['center'][1] - self.identify_cell[i]['radius'])),
                          (0, 255, 0), 2)
        return img

    def draw_bounding_box(self):
        bounding_img = self.get_rgb()
        for index, info in self.identify_cell.items():
            cv2.rectangle(bounding_img,
                          (int(info['center'][0] - info['radius']), int(info['center'][1] + info['radius'])),
                          (int(info['center'][0] + info['radius']), int(info['center'][1] - info['radius'])),
                          (255, 0, 0), 2)
            # cv2.putText(bounding_img,
            #             str(index), info['center'],
            #             cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
        plt.imshow(bounding_img)
        plt.show()
        return bounding_img

    def _contrast_stretch(self,img):
        a, b = np.min(img), np.max(img)
        hist, bins = np.histogram(img.ravel(), b - a + 1, [a, b + 1])
        c, d = (hist != 0).argmax(), b - a - (hist[::-1] != 0).argmax()
        c, d = bins[c], bins[d]
        a, b = 0, 255
        ConStreImg = (img - c) / (d - c) * (b - a) + a
        return np.array(ConStreImg).astype('uint8')


    def pre_processing(self):
        # normalize
        # img = self.original_img.copy().astype(np.float32)
        # img -= np.mean(img)
        # img /= np.linalg.norm(img)
        # img = np.clip(img, 0, 255)
        # img *= (1. / float(img.max()))
        # img = (img * 255).astype(np.uint8)
        # self.normalize_img = img.copy()
        # kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
        # img = cv2.morphologyEx(img, cv2.MORPH_OPEN, kernel)
        # kernel = np.ones((3, 3), np.uint8)  # 进行腐蚀膨胀操作
        # erosion = cv2.erode(img, kernel, iterations=3)
        # dilation = cv2.dilate(img, kernel, iterations=3)
        # img = cv2.subtract(dilation, erosion)
        # _, self.thresh = cv2.threshold(img, 15, 1, cv2.THRESH_BINARY)
        # return cv2.findContours(self.thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)[1]

        # 第二组图
        # img = self.original_img.copy().astype(np.int16)
        # # img = cv2.imread(filename, 0)
        # img = self._contrast_stretch(img)
        # hist, _ = np.histogram(img.flatten(), 256, [0, 256])
        # bg = np.argmax(hist)
        # img[img <= bg] = 0
        # kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        # img = cv2.morphologyEx(img, cv2.MORPH_OPEN, kernel)
        # img = cv2.equalizeHist(img)
        # img = cv2.equalizeHist(img)
        # self.thresh = img
        # self.normalize_img = img.copy()

        # 第三幅图
        img = self.original_img.copy().astype(np.int16)
        median = np.median(img)
        img = img.astype(np.float) - median
        median *= 2
        img[img < 0] /= median
        img[img > 0] /= 510 - median


        img -= np.mean(img)
        img /= np.linalg.norm(img)
        img = np.clip(img, 0, 255)
        img *= (1. / float(img.max()))
        img = (img * 255).astype(np.uint8)
        self.normalize_img = img.copy()

        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        img = cv2.morphologyEx(img, cv2.MORPH_OPEN, kernel)
        img = cv2.morphologyEx(img, cv2.MORPH_CLOSE, kernel)
        _, self.thresh = cv2.threshold(img, 70, 1, cv2.THRESH_BINARY)


        # normalize
        # img = self.original_img.copy().astype(np.float32)
        # img -= np.mean(img)
        # img /= np.linalg.norm(img)
        # img = np.clip(img, 0, 255)
        # img *= (1. / float(img.max()))
        # img = (img * 255).astype(np.uint8)
        # self.normalize_img = img.copy()
        # kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        # img = cv2.morphologyEx(img, cv2.MORPH_OPEN, kernel)
        # img = cv2.morphologyEx(img, cv2.MORPH_CLOSE, kernel)
        # _, self.thresh = cv2.threshold(img, 15, 1, cv2.THRESH_BINARY)

        # plt.imshow(self.thresh, 'gray')
        # plt.show()
        return cv2.findContours(self.thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)[0]


def get_distance(p1, p2):
    return math.sqrt(((p1[0] - p2[0])**2) + ((p1[1] - p2[1])**2))


class Tracker:
    def __init__(self, path):
        self.sequences = []
        previous_img = None

        for root, dirs, files, in os.walk(path):
            files.sort()
            cou = 0
            for file in files:
                if ".tif" in file:
                    self.sequences.append(Obj(os.path.join(root, file), previous_img))
                    previous_img = self.sequences[-1]
                    cou += 1
                if cou == 200:
                    break

    def speed(self, index):
        cur = self.sequences[index]
        img = cur.normalize_img.copy()
        prev = cur.prev
        for idx, info in cur.identify_cell.items():
            if prev is not None and idx in prev.identify_cell:
                speed = str(round(get_distance(cur.identify_cell[idx]['center'], prev.identify_cell[idx]['center']), 2))
            else:
                speed = 0
            cv2.putText(img,
                        str(speed),
                        info['center'],
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2,
                        (255, 0, 0), 2)
        return img

    def total_distance(self, index):
        cur = self.sequences[index]
        img = cur.normalize_img.copy()
        for idx, info in cur.identify_cell.items():
            initial = index - 1
            path = 0
            while initial >= 0:
                if idx in self.sequences[initial].identify_cell:
                    path += get_distance(self.sequences[initial+1].identify_cell[idx]['center'],
                                         self.sequences[initial].identify_cell[idx]['center'])
                    initial -= 1
                else:
                    break
            cv2.putText(img,
                        str(round(path, 2)),
                        info['center'],
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2,
                        (255, 0, 0), 2)
        return img

    def net_distance(self, index):
        cur = self.sequences[index]
        img = cur.normalize_img.copy()
        for idx, info in cur.identify_cell.items():
            initial = index - 1
            while initial >= 0:
                if idx in self.sequences[initial].identify_cell:
                    initial -= 1
                else:
                    break
            cv2.putText(img,
                        str(round(get_distance(cur.identify_cell[idx]['center'],
                                               self.sequences[initial+1].identify_cell[idx]['center']), 2)),
                        info['center'],
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2,
                        (255, 0, 0), 2)
        return img

    def confinement_ratio(self, index):
        cur = self.sequences[index]
        img = cur.normalize_img.copy()
        for idx, info in cur.identify_cell.items():
            initial = index - 1
            path = 0
            while initial >= 0:
                if idx in self.sequences[initial].identify_cell:
                    initial -= 1
                    path += get_distance(self.sequences[initial+1].identify_cell[idx]['center'],
                                         self.sequences[initial].identify_cell[idx]['center'])
                else:
                    break
            ratio = path / get_distance(cur.identify_cell[idx]['center'],
                                        self.sequences[initial+1].identify_cell[idx]['center'])
            cv2.putText(img,
                        str(round(ratio, 2)),
                        info['center'],
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2,
                        (255, 0, 0), 2)
        return img

    def draw_tracking_path(self):
        for i in range(len(self.sequences) - 1):
            current_img = self.sequences[i]
            next_img = self.sequences[i + 1]
            background_image = next_img.get_rgb()
            for index, info in current_img.identify_cell.items():
                if index in next_img.identify_cell:
                    if get_distance(info['center'], next_img.identify_cell[index]['center']) > 1:
                        background_image = cv2.line(background_image, info['center'], next_img.identify_cell[index]['center'], (0, 0, 255), 3)

            for index, info in next_img.identify_cell.items():
                cv2.rectangle(background_image,
                              (int(info['center'][0] - info['radius']), int(info['center'][1] + info['radius'])),
                              (int(info['center'][0] + info['radius']), int(info['center'][1] - info['radius'])),
                              (0, 255, 0), 1)
                cv2.putText(background_image,str(index), (info['center'][0]+10, info['center'][1]-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 1)

            cv2.putText(background_image, f'Total Cells #: {len(current_img.identify_cell)}', (10,50),cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 0, 0), 2)
            background_image = cv2.cvtColor(background_image,cv2.COLOR_BGR2RGB)
            cv2.imwrite(f'/Users/jasonwang/Downloads/2020T2_COMP9517/Assignments_and_Projects/Proj/Dataset/PhC-C2DL-PSC/Sequence 1 Track/tracking_path{i}.tif', background_image)

            background_image = None
        return background_image


if __name__ == '__main__':
    # obj1 = Obj("/Users/ysk/Downloads/UNSW_20T2_COMP9517_Project-master/COMP9517 20T2 Group Project Image Sequences/Fluo-N2DL-HeLa/Sequence 1/t000.tif", None)
    # obj2 = Obj("/Users/ysk/Downloads/UNSW_20T2_COMP9517_Project-master/COMP9517 20T2 Group Project Image Sequences/Fluo-N2DL-HeLa/Sequence 1/t001.tif", obj1)

    # Wilson's image path
    dataset_path = '/Users/jasonwang/Downloads/2020T2_COMP9517/Assignments_and_Projects/Proj/Dataset/PhC-C2DL-PSC/Sequence 1/'
    dataset_1 = f'{dataset_path}DIC-C2DH-HeLa'
    dataset_2 = f'{dataset_path}Fluo-N2DL-HeLa'
    dataset_3 = f'{dataset_path}PhC-C2DL-PSC'

    tracker = Tracker(dataset_path)
    # tracker.draw_tracking_path()
    img = tracker.total_distance(2)
    plt.imshow(img)
    plt.show()

    # obj1 = Obj("/Users/jasonwang/Downloads/2020T2_COMP9517/Assignments_and_Projects/Proj/Dataset/PhC-C2DL-PSC/Sequence 1/t100.tif", None)
    # obj1.draw_bounding_box()
    # plt.imshow(obj1.thresh, 'gray')
    # plt.show()
