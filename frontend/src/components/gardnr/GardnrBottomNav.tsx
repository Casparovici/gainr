import { useQuery } from "@tanstack/react-query";

import { gardnrApi } from "../../api/gardnrClient";
import { MODULE_NAV } from "../../config/moduleNav";
import KitBottomNav from "../ui/KitBottomNav";
import { taskCounts } from "./ui";

/** gardnr's bottom bar on a phone: the kit's bar, with a count of overdue tasks on Vandaag so
 * they're visible from any gardnr page. Same destinations and order as the desktop tab strip. */
export default function GardnrBottomNav() {
  const plantsQuery = useQuery({ queryKey: ["gardnr-plants", false], queryFn: () => gardnrApi.listPlants(false) });
  const overdue = plantsQuery.data ? taskCounts(plantsQuery.data).total.late : 0;

  return (
    <KitBottomNav
      items={MODULE_NAV.gardnr}
      label="gardnr"
      badges={{ "/gardnr/vandaag": { count: overdue, label: `${overdue} te laat` } }}
    />
  );
}
