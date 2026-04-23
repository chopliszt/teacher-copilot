import { useQuery } from '@tanstack/react-query';
import type { ScheduleResponse } from '../api/client';

export function useSchedule() {
  return useQuery<ScheduleResponse, Error>({
    queryKey: ['schedule'],
    queryFn: async () => ({
      school: "IB High School",
      teacher: "TeacherPilot PM",
      semester: "Spring 2026",
      homeroom: {
        time: "08:00",
        room: "Room 12",
        group: "9C Homeroom",
        days: [1,2,3,4,5]
      },
      current_day: 3,
      break: "10:00",
      lunch: "13:00",
      classes: [
        {
          day: 3,
          periods: [
            { time: "08:00", subject: "Homeroom", room: "Room 12", group: "9C" },
            { time: "11:30", subject: "Digital Design", room: "Lab A", group: "Grade 10" },
            { time: "14:00", subject: "Faculty Training", room: "Meeting Rm", group: "AI Committee" }
          ]
        }
      ]
    }),
    staleTime: Infinity,
  });
}
