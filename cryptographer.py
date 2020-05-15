from PIL import Image, ImageDraw
from cryptography.fernet import Fernet
import datetime
import base64


class Cryptographer:

    def __init__(self, image, key, text="decrypt"):
        """
        Класс для шифрования/дешифрования текста в изображение.

        :param image: Изображение для шифрования/дешифрования.
        :param key: Ключ для шифрования/дешифрования.
        :param text: Текст для шифрования.
        """
        self.image = Image.open(image)
        self.text = text
        self.key = self.update_key(key)
        self.draw = ImageDraw.Draw(self.image)
        self.width = self.image.size[0]
        self.height = self.image.size[1]
        self.pix = self.image.load()
        # Массивы для дискретного косинусного преобразования
        self.cos_t = [
            [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
            [0.9807853, 0.8314696, 0.5555702, 0.1950903, -0.1950903, -0.5555702, -0.8314696, -0.9807853],
            [0.9238795, 0.3826834, -0.3826834, -0.9238795, -0.9238795, -0.3826834, 0.3826834, 0.9238795],
            [0.8314696, -0.1950903, -0.9807853, -0.5555702, 0.5555702, 0.9807853, 0.1950903, -0.8314696],
            [0.7071068, -0.7071068, -0.7071068, 0.7071068, 0.7071068, -0.7071068, -0.7071068, 0.7071068],
            [0.5555702, -0.9807853, 0.1950903, 0.8314696, -0.8314696, -0.1950903, 0.9807853, -0.5555702],
            [0.3826834, -0.9238795, 0.9238795, -0.3826834, -0.3826834, 0.9238795, -0.9238795, 0.3826834],
            [0.1950903, -0.5555702, 0.8314696, -0.9807853, 0.9807853, -0.8314696, 0.5555702, -0.1950903]
        ]
        self.e = [
            [0.125, 0.176777777, 0.176777777, 0.176777777, 0.176777777, 0.176777777, 0.176777777, 0.176777777],
            [0.176777777, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25],
            [0.176777777, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25],
            [0.176777777, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25],
            [0.176777777, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25],
            [0.176777777, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25],
            [0.176777777, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25],
            [0.176777777, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25]
        ]

    def dct(self, dct, arr):
        """
        Дискретное косинусное преобразование.

        :param dct: Массив для записи результата преобразования.
        :param arr: Массив с пикселями.
        :returns: Массив после дискретного косинусного преобразования.
        """
        for i in range(8):
            for j in range(8):
                temp = 0.0
                for x in range(8):
                    for y in range(8):
                        temp = temp + self.cos_t[i][x] * self.cos_t[j][y] * arr[x][y][2]
                dct[i][j] = self.e[i][j] * temp
        return dct

    def idct(self, dct, arr):
        """
        Обратное дискретное косинусное преобразование.

        :param dct: Массив c дискретного косинусными значениями.
        :param arr: Массив для записи результата преобразования.
        :returns: Массив после обратного дискретного косинусного преобразования.
        """
        for i in range(8):
            for j in range(8):
                temp = 0
                for x in range(8):
                    for y in range(8):
                        temp += dct[x][y] * self.cos_t[x][i] * self.cos_t[y][j] * self.e[x][y]
                        if temp > 255:
                            tmp = 255
                        elif temp < 0:
                            tmp = 0
                        else:
                            tmp = round(temp)
                        arr[i][j][2] = tmp
        return arr

    @staticmethod
    def text_to_bits(text, encoding='utf-8', errors='surrogatepass'):
        """
        Преобразование текста в биты.

        :param text: Текст для преобразования.
        :param encoding: Кодировка текста.
        :param errors: Значение для ошибок.
        :returns: Массив битов из текста.
        """
        bits = bin(int.from_bytes(text.encode(encoding, errors), 'big'))[2:]
        return bits.zfill(8 * ((len(bits) + 7) // 8))

    @staticmethod
    def text_from_bits(bits, encoding='utf-8', errors='surrogatepass'):
        """
        Преобразование битов в текст.

        :param bits: Биты для преобразования.
        :param encoding: Кодировка текста.
        :param errors: Значение для ошибок.
        :returns: Текст полученный из битов.
        """
        n = int(bits, 2)
        return n.to_bytes((n.bit_length() + 7) // 8, 'big').decode(encoding, errors) or '\0'

    def encrypt(self):
        """
        Шифрование текста в изображение.

        :param self: Данные класса для шифрования.
        :returns: Изображение с зашифрованным текстом.
        """
        dct = [[0] * 8 for i in range(8)]
        temp = [[0] * 8 for i in range(8)]
        cur = 0
        # Шифрование текста по ключу с помощью класса Fernet
        cipher = Fernet(self.key)
        self.text = bytes(self.text, "utf-8")
        self.text = cipher.encrypt(self.text).decode()

        bytes_str = self.text_to_bits(self.text)

        for i in range(0, self.width - 1, 8):
            for j in range(0, self.height - 1, 8):
                if cur >= len(bytes_str):
                    break
                for x in range(8):
                    for y in range(8):
                        temp[x][y] = [
                            self.pix[x + j, y + i][0],
                            self.pix[x + j, y + i][1],
                            self.pix[x + j, y + i][2]
                        ]
                dct = self.dct(dct, temp)
                k = abs(dct[3][4]) - abs(dct[4][3])
                if bytes_str[cur] == '1':
                    if k <= 25:
                        dct[3][4] = (abs(dct[4][3]) + 150) if dct[3][4] >= 0 else -1 * (abs(dct[4][3]) + 150)
                else:
                    if k >= -25:
                        dct[4][3] = (abs(dct[3][4]) + 150) if dct[4][3] >= 0 else -1 * (abs(dct[3][4]) + 150)
                temp = self.idct(dct, temp)
                for x in range(8):
                    for y in range(8):
                        self.draw.point((x + j, y + i), (temp[x][y][0], temp[x][y][1], temp[x][y][2]))
                cur += 1
            if cur >= len(self.text) * 8:
                break
        path = f"photo/encrypt/after/{datetime.datetime.today().strftime('%Y-%m-%d-%H.%M.%S') + 'crypto.png'}"
        self.image.save(path, "PNG")
        return path

    def decrypt(self):
        """
        Дешифрование текста из изображения.

        :param self: Данные класса для дешифрования.
        :returns: Дешифрованный текст.
        """
        end = False
        bytes_str = ""
        dct = [[0] * 8 for i in range(8)]
        temp = [[0] * 8 for i in range(8)]
        for i in range(0, self.width - 1, 8):
            for j in range(0, self.height - 1, 8):
                for x in range(8):
                    for y in range(8):
                        temp[x][y] = [
                            self.pix[x + j, y + i][0],
                            self.pix[x + j, y + i][1],
                            self.pix[x + j, y + i][2]
                        ]
                dct = self.dct(dct, temp)
                k = abs(dct[3][4]) - abs(dct[4][3])
                if k >= 25:
                    bytes_str += "1"
                elif k <= -25:
                    bytes_str += "0"
                else:
                    end = True
                    break
            if end:
                break
        self.text = self.text_from_bits(bytes_str)
        self.text = self.text.encode()
        cipher = Fernet(self.key)
        try:
            self.text = cipher.decrypt(self.text).decode("utf-8")
        except Exception as e:
            return "Incorrect key!"
        return self.text

    @staticmethod
    def update_key(raw_key):
        """
        Преобразование ключа в подходящий для шифрования/дешифрования.

        :param raw_key: Исходный ключ.
        :returns: Преобразованный ключ.
        """
        key = raw_key
        while len(key) < 32:
            key += raw_key
        return base64.urlsafe_b64encode(bytes(key[:32], "utf-8")[:32])
