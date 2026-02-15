import { useRef, useEffect, useCallback } from "react";
import { Box, Heading, Spinner, Text, Badge, Flex } from "@chakra-ui/react";
import { useLogs } from "../../hooks/useLogs";

const levelColor: Record<string, string> = {
  INFO: "blue",
  WARNING: "yellow",
  ERROR: "red",
  DEBUG: "gray",
  CRITICAL: "red",
};

export default function LogPanel() {
  const { data, isLoading, isError } = useLogs();
  const containerRef = useRef<HTMLDivElement>(null);
  const isNearBottom = useRef(true);

  const handleScroll = useCallback(() => {
    const el = containerRef.current;
    if (!el) return;
    const threshold = 60;
    isNearBottom.current =
      el.scrollHeight - el.scrollTop - el.clientHeight < threshold;
  }, []);

  useEffect(() => {
    if (isNearBottom.current && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [data]);

  if (isLoading) return <Spinner />;
  if (isError) return <Text color="red.400">Failed to load logs</Text>;

  const logs = data?.logs ?? [];

  return (
    <Box bg="gray.800" borderRadius="lg" p={4}>
      <Heading size="sm" mb={3}>
        System Logs
      </Heading>
      <Box
        ref={containerRef}
        onScroll={handleScroll}
        maxH="300px"
        overflowY="auto"
        fontFamily="mono"
        fontSize="xs"
        bg="gray.900"
        borderRadius="md"
        p={3}
      >
        {logs.length === 0 ? (
          <Text color="gray.500">No logs available</Text>
        ) : (
          logs.map((log, i) => (
            <Flex key={i} gap={2} py={0.5} flexWrap="wrap">
              <Text color="gray.500" flexShrink={0}>
                {log.timestamp}
              </Text>
              <Badge
                colorScheme={levelColor[log.level] ?? "gray"}
                fontSize="xx-small"
                flexShrink={0}
              >
                {log.level}
              </Badge>
              <Text wordBreak="break-all">{log.message}</Text>
            </Flex>
          ))
        )}
      </Box>
    </Box>
  );
}
