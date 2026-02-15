import { Badge } from "@chakra-ui/react";

interface StatusBadgeProps {
  status: string;
}

export default function StatusBadge({ status }: StatusBadgeProps) {
  const colorScheme = status === "running" ? "green" : "red";
  return (
    <Badge colorScheme={colorScheme} fontSize="sm" px={2} py={1} borderRadius="md">
      {status === "running" ? "Running" : "Stopped"}
    </Badge>
  );
}
