import { Box, Stat, StatLabel, StatNumber } from "@chakra-ui/react";
import type { ReactNode } from "react";

interface StatCardProps {
  label: string;
  value: string | number;
  color?: string;
  children?: ReactNode;
}

export default function StatCard({ label, value, color, children }: StatCardProps) {
  return (
    <Box bg="gray.800" borderRadius="lg" p={4}>
      <Stat>
        <StatLabel color="gray.400" fontSize="xs">
          {label}
        </StatLabel>
        <StatNumber fontSize="xl" color={color}>
          {value}
        </StatNumber>
        {children && <Box mt={1}>{children}</Box>}
      </Stat>
    </Box>
  );
}
