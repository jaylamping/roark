from secimg import *
sec([0,424.86,0],[0,1,0],[0,2],'Section A: horizontal plane Y 424.86 through the pitch axis (X) and roll axis (Z). Looking down; +Z forward, +X outboard.',
    'S1_pitch_axis_section.png',(30,240),(-70,90),
    axes=[(30,0,235,0,'pitch axis'),(170.49,-60,170.49,85,'roll axis')],
    notes=[(97,-52,'pitch output face X 97'),(120.2,-64,'roll housing X 120.2'),(117.6,12,'P1 web 2.6 mm from roll RS03 side rib'),(170,30.6,'roll output Z 30.64'),(170,50.6,'spacer / P2 face Z 50.64'),(75,60,'cage side X 75')])
sec([170.49,0,0],[1,0,0],[2,1],'Section B: plane X 170.49 through the roll axis (Z) and yaw axis (Y). Looking from outboard; +Z forward to the right.',
    'S2_roll_axis_section.png',(-70,90),(270,490),
    axes=[(-65,424.86,85,424.86,'roll axis'),(5.99,280,5.99,480,'yaw axis')],
    notes=[(30.6,440,'roll output'),(39.5,470,'P1 lip end Z 39.5'),(6,365.3,'RS02 rear Y 365.26 (2.1 mm to P1)'),(6,319.9,'RS02 output / hub Y 319.86'),(30,322,'3.4 mm hub-to-RS02 gap')])
sec([0,0,5.99],[0,0,1],[0,1],'Section C: frontal plane Z 5.99 through the yaw axis (Y) and pitch axis (X). Looking from the front; +X outboard to the right.',
    'S3_yaw_axis_section.png',(30,250),(270,500),
    axes=[(170.49,280,170.49,495,'yaw axis'),(35,424.86,245,424.86,'pitch axis')],
    notes=[(75,480,'cage side X 75'),(140,360,'RS02 socket side (inboard)')])
