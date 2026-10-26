import React from "react";
import MangaWorkspaceView, { MangaWorkspaceViewProps } from "./MangaWorkspaceView";

export const MangaPuppeteeringView: React.FC<MangaWorkspaceViewProps> = (props) => {
  return <MangaWorkspaceView {...props} initialMode="puppeteering" />;
};

export default MangaPuppeteeringView;
