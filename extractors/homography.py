import cv2
from skimage import io
import matplotlib.pyplot as plt

from skimage.viewer import ImageViewer
from skimage.transform import ProjectiveTransform
import numpy as np
import math
# points_img = np.array([
#     [874,716],
#     [1257,556],
#     [1266,44],
#     [1200,328],
#     [1072,303],
#     [441,362],
#     [286,420],
#     [368,535]
# ])

# points_sim = np.array([
#     [200,0],
#     [350,100],
#     [350,200],
#     [300,300],
#     [100,300],
#     [0,200],
#     [0,100],
#     [100,0]
# ])

points_img = np.array([
    [4,645],[0,717],[297,719],
    [878,719],[500,636],[236,582],[950,625],[654,565],
    [468,510],[674,548],[991,602],[1117,567],[760,512],
    [502,474],[496,473],[504,464],[643,427],[568,416],
    [444,446],[530,410],[409,443],[251,416],[377,385],
    [451,368],[659,389],[737,395],[771,388],[827,385],
    [967,404],[990,391],[840,379],[917,353],[1035,365],
    [1200,367],[1155,410],[1156,425],[1177,429],[1194,438],
    [1265,445],[1264,495],[1177,487],[1260,554],[1143,560],
    [1136,566],[878,444],[95,628],
    # [10,560],[207,512],[244,446],[391,470],[454,360],
    # [473,347],[742,357],[889,359],[810,380],[683,388],
    # [571,366],[1179,430],[1223,411],[1254,429],[1098,585],
    # [1216,577],[1196,712],[937,709]
    


])
# points_sim = np.array([
#     [-6.,-16.5],[-3.,-17.5],[0.,-15.5],
#     [6.,-14.],[0.,-14.],[-6.,-14.],[6.,-10.],[0.,-10.],
#     [-6.,-9.],[0.,-9.],[6.,-9.],[6.,-9.],[0.,-9.],
#     [-6.,-7.],[-6.5,-6.5],[-7.,-6.],[-7.,1.],[-9.,6.5],
#     [-9.,-6.],[-10.,6.5],[-10.,-6.],[-14.,-6.],[-14.,6.5],
#     [-14.,6.],[-9.,6.],[-7.,6.],[-6.5,6.5],[-6.,7.],
#     [0.,7.],[0.,9.],[-6.,9.],[-6.,15.5],[0.,15.5],
#     [6.,15.5],[6.,9.],[6.,7.],[6.5,6.5],[7.,6.],
#     [9.0,6.],[9.,6.5],[7.,6.5],[9.,-6.],[7.,-6.],
#     [6.5,-6.5],[0.,6.5],[-6.,-15.]
# ]) 
points_sim = np.array([
    [-6.,-16.5],[-3.,-17.5],[0.,-15.5],
    [6.,-14.],[0.,-14.],[-6.,-14.],[6.,-10.],[0.,-10.],
    [-6.,-9.],[0.,-9.],[6.,-9.],[6.,-9.],[0.,-9.],
    [-6.,-7.],[-6.5,-6.5],[-7.,-6.],[-7.,0.],[-9.,0.],
    [-9.,-6.],[-10.,0.],[-10.,-6.],[-14.,-6.],[-14.,0.],
    [-14.,6.],[-9.,6.],[-7.,6.],[-6.5,6.5],[-6.,7.],
    [0.,7.],[0.,9.],[-6.,9.],[-6.,15.5],[0.,15.5],
    [6.,15.5],[6.,9.],[6.,7.],[6.5,6.5],[7.,6.],
    [9.0,6.],[9.,0.],[7.,0.],[9.,-6.],[7.,-6.],
    [6.5,-6.5],[0.,0.],[-6.,-15.],

    # [-7.5,-15.5],[-7.5,-12],[-10.5,-8],[-7.5,8],[-19,6],
    # [-19,9],[-9.5,9.5],[-6,15],[-6,10],[-10,7],
    # [-15.5,7.5],[6.5,6.5],[7.5,7.5],[8.5,7],[7,-8.5],
    # [9,-8.5],[9,-12.5],[7,-12.5]
])

# points_img = np.array([
#     [878,719],[500,636],[236,582],[950,625],[654,565],
#     [468,510],[674,548],[991,602],[1117,567],[760,512],
#     [502,474],[496,473],[504,464],[643,427],[568,416],
#     [444,446],[530,410],[409,443],[251,416],[377,385],
#     [451,368],[659,389],[737,395],[771,388],[827,385],
#     [967,404],[990,391],[840,379],[917,353],[1035,365],
#     [1200,367],[1155,410],[1156,425],[1177,429],[1194,438],
#     [1265,445],[1264,495],[1177,487],[1260,554],[1143,560],
#     [1136,566],[878,444],
#     [0.,717.],[143.,716.],[269.,714.],[165.,675.],[0.,674,],
#     [0.,636.],[153.,601.],[265.,638.],[400.,663.],[445.,676.],
#     [379.,719.],[618.,715.],[773.,719.]
# ])
 
# points_sim = np.array([
#     [6.,-14.],[0.,-14.],[-6.,-14.],[6.,-10.],[0.,-10.],
#     [-6.,-9.],[0.,-9.],[6.,-9.],[6.,-9.],[0.,-9.],
#     [-6.,-7.],[-6.5,-6.5],[-7.,-6.],[-7.,0.],[-9.,0.],
#     [-9.,-6.],[-10.,0.],[-10.,-6.],[-14.,-6.],[-14.,0.],
#     [-14.,6.],[-9.,6.],[-7.,6.],[-6.5,6.5],[-6.,7.],
#     [0.,7.],[0.,9.],[-6.,9.],[-6.,15.5],[0.,15.5],
#     [6.,15.5],[6.,9.],[6.,7.],[6.5,6.5],[7.,6.],
#     [9.0,6.],[9.,0.],[7.,0.],[9.,-6.],[7.,-6.],
#     [6.5,-6.5],[0.,0.],
#     [-3.,-17.5],[-1.5,-16.5],[0.,-15.5],[-3.,-15.5],[-4.5,-16.5],
#     [-3.,-15.5],[-3.,-14.75],[-1.5,-14.75],[-0.5,-14.75],[0.5,-14.75],
#     [0.5,-15.5],[3.,14.75],[4.5,14.35]
# ])
# yp = [91.,40.]
# y = [0.,1.]
# norm_yp = np.linalg.norm(yp)

# yp /= norm_yp
# theta = np.arccos(np.dot(y,yp))
# print(theta)
# R = [[np.cos(theta),-np.sin(theta)],
#     [np.sin(theta),np.cos(theta)]
# ]
# print(R)
# yp = [91.,40.]
# print(np.matmul(R,yp).tolist())
center = [878,444]
points_img_centered = [ ]
for p in points_img:
    new_p = np.subtract(p,center).tolist()
    new_p[1] *= -1.
    # new_p = np.matmul(R,new_p).tolist()
    points_img_centered.append(new_p)
points_img_centered = np.array(points_img_centered )
# print(points_img_centered)
# plt.scatter([p[0] for p in points_sim],[p[1] for p in points_sim])
# plt.scatter([p[0] for p in points_img_centered],[p[1] for p in points_img_centered])
# plt.show()


tr = ProjectiveTransform()

print(tr.estimate(points_sim,points_img_centered))

print(tr.params)

np.savetxt("./datasets/bad/homography/homography.txt",tr.params)

