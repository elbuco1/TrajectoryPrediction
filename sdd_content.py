import sys
import json
import csv 
import helpers
import numpy as np

import pandas as pd 

# python sdd_content.py parameters/data.json parameters/prepare_training.json
def main():
    args = sys.argv
    # data = json.load(open(args[1]))
    # prepare = json.load(open(args[2]))

    data = json.load(open("parameters/data.json"))
    prepare = json.load(open("parameters/prepare_training.json"))

    scene_list = prepare["selected_scenes"]
    scene_path = data["preprocessed_datasets"] +"{}.csv"
    frames_temp = data["temp"] + "frames.txt"
    reports_path = data["reports"] + "{}.csv"
   
    standard_split = [
        "coupa0", 
        "coupa1", 
        "gates2", 
        "hyang0", 
        "hyang1", 
        "hyang3", 
        "hyang8", 
        "little0", 
        "little1", 
        "little2", 
        "little3", 
        "nexus5", 
        "nexus6", 
        "quad0", 
        "quad1", 
        "quad2", 
        "quad3"
    ]
    
    
    columns = [
        'pedestrian',
            'skate' ,
            'car' ,
            'bus' ,
            'bicycle',
            'cart' ,
            'total'
    ]
    indexes = [scene for scene in scene_list]

    

    stats = stats_scenes(scene_list,columns,scene_path,frames_temp)

    
    table_types_nb = draw_table(indexes,columns,"scene",stats)
    
    save_table(table_types_nb,scene_list,reports_path.format("nb"))
    save_table(table_types_nb,standard_split,reports_path.format("nb_standard_split"))

    

    table_types_max_frame = draw_table(indexes,columns,"frames",stats)
    save_table(table_types_max_frame,scene_list,reports_path.format("max"))
    save_table(table_types_max_frame,standard_split,reports_path.format("max_standard_split"))
    

def save_table(table,ids,path):
    table = table.loc[ids]
    table.to_csv(path)

def stats_scenes(scene_list,columns,scene_path,frames_temp):
    types = {}
    
    for scene in scene_list:

        types[scene] = {"scene": {},"frames": {}}

        seen_ids = []

        

        for c in columns:
            types[scene]["frames"][c] = [0]
            types[scene]["scene"][c] = 0

        

        helpers.extract_frames(scene_path.format(scene),frames_temp,save = True)
        

        with open(frames_temp) as frames:
            for i,frame in enumerate(frames):
                frame = json.loads(frame)

                for id_ in frame["ids"]:
                    type_ = frame["ids"][id_]["type"]
                    types[scene]["frames"][type_][-1] += 1
                    types[scene]["frames"]["total"][-1] += 1

                    if id_ not in seen_ids:
                        types[scene]["scene"][type_] += 1
                        types[scene]["scene"]["total"] += 1
                        seen_ids.append(id_)


                for key in types[scene]["frames"]:
                    types[scene]["frames"][key].append(0)

                    

            report_types = {"max":{}}
            for key in types[scene]["frames"]:
                # report_types["max"][key] = np.max(types[scene]["frames"][key])
                # report_types["max"][key] = np.max(types[scene]["frames"][key])

                types[scene]["frames"][key ] = np.max(types[scene]["frames"][key])

            # types[scene]["frames"] = report_types
    return types


def draw_table(indexes,columns,attribute,stats):
    rows = []

    for scene in indexes:
        row = []
        report = stats[scene]
        for column in columns:
            row.append(report[attribute][column])
        rows.append(row)

        
    table = pd.DataFrame(rows,index= indexes,columns=columns)

    return table
    


        


    #     print("{}: mean {}, std {}".format(scene,np.mean(nb_agents_scene),np.std(nb_agents_scene)))
    #     print(" max {}, min {}, nb_frames {}, nb_agents {}".format(np.max(nb_agents_scene),np.min(nb_agents_scene),i+1,np.sum(nb_agents_scene)))
    #     print("types {}".format(report_types))
    #     print("")


        

    #     helpers.remove_file(frames_temp)
    # print(" mean {}, std {}".format(np.mean(nb_agents_scenes),np.std(nb_agents_scenes)))
    # print(" max {}, min {}".format(np.max(nb_agents_scenes),np.min(nb_agents_scenes)))


if __name__ == "__main__":
    main()