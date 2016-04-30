#!/usr/bin/env python

image_c_style_path = "/home/chenqiang/nce/linux_nce_8bits.c"
image_out_path = "/home/chenqiang/nce/image_out"

# origin color set
color_set_head_list = ['0x42', '0x4d', '0x50', '0x08', '0x02', '0x80', '0x01', '0xe0', '0xff', '0x01', '0x19', '0x00']

color_set_mid_list = ['0x20', '0x10', '0x00', '0x00', '0x30', '0x00', '0x02','0x03', '0x05', '0x00', '0x05', '0x10']

color_set_tail_list = ['0x05', '0x00', '0x19', '0x01']


# generate color set
gen_bmp_list = []

# print split_hex("0x1234567")
# >>> ['0x12', '0x34', '0x56']
def split_hex(value):
    value = value[2:] if len(value) % 2 == 0 else "0" + value[2:]
    return ['0x'+value[i:i+2] for i in range(0, len(value), 2)]

def color_set():
    result_list = []
    gen_list = []
    try:
        with open(image_c_style_path, 'r') as f:
            start_flag = False
            for line in f:
                if line.startswith("const GUI_COLOR Colors"):
                    start_flag = True
                elif line.startswith("};"):
                    start_flag = False
                    break
                else:
                    if start_flag is True:
                        # remove more space and '\n', such as: '    ' -> ''
                        line_list = line.strip().split(',')
                        # remove '' string.
                        line_list = filter(None, line_list)
                        line_list = [split_hex(i) for i in line_list]
                        # list contacts list
                        result_list.extend(line_list)
                    continue
    except:
        print "open or handle file error!"
    finally:
        address = 0
        for color in result_list:
            # write 1-color address
            #print "color", color
            gen_list.append('0x21')
            gen_list.append(hex(address) if address >=16 else '0x0' + hex(address)[2:])
            address += 1
            i = 0
            # R,G,B
            for single in color:
                # choose write single-color (such as R,G,B) address
                gen_list.append('0x20')
                gen_list.append(hex(21+i))
                i += 1
                # choose write single-color (such as R,G,B) data
                gen_list.append('0x22')
                gen_list.append(single)
        pass
    return gen_list


def data_set():
    result_list = []
    gen_list = []
    try:
        with open(image_c_style_path, 'r') as f:
            start_flag = False
            for line in f:
                if line.startswith("const unsigned char acnce_8bits_2"):
                    start_flag = True
                else:
                    if start_flag is True:
                        if line.startswith("};"):
                            start_flag = False
                            break
                        else:
                            # remove more space and '\n', such as: '    ' -> ''
                            line_list = line.strip().split(',')
                            # remove '' string.
                            line_list = filter(None, line_list)
                            # list contacts list
                            result_list.extend(line_list)
                    continue
    except:
        print "open or handle file error!"
    finally:
        address = 0
        for data in result_list:
            # write data address
            gen_list.append('0x18')
            gen_list.append(data)
        pass
    return gen_list

def write_file(image_list):
    try:
        with open(image_out_path, 'w') as f:
            count = 0
            for item in image_list:
                f.write("%s," % item.strip())
                count += 1
                if count == 16:
                    f.write("\n")
                    count = 0
    except:
        print "open or handle file error!"
    finally:
        pass

def main():
    color_set_list = color_set()
    data_set_list = data_set()
    image_list = color_set_head_list + color_set_list + color_set_mid_list + data_set_list + color_set_tail_list
    #print image_list
    write_file(image_list)


if __name__ == "__main__":
    main()
