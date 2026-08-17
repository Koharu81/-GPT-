CREATE TABLE `chatHistory` (
	`id` int AUTO_INCREMENT NOT NULL,
	`userId` int NOT NULL,
	`role` enum('user','assistant') NOT NULL,
	`content` text NOT NULL,
	`mode` varchar(40),
	`modelVersion` varchar(80),
	`createdAt` timestamp NOT NULL DEFAULT (now()),
	CONSTRAINT `chatHistory_id` PRIMARY KEY(`id`)
);
--> statement-breakpoint
CREATE TABLE `modelVersions` (
	`id` int AUTO_INCREMENT NOT NULL,
	`userId` int NOT NULL,
	`version` varchar(80) NOT NULL,
	`label` varchar(120) NOT NULL,
	`description` text,
	`datasetRecords` int NOT NULL DEFAULT 0,
	`requestedSteps` int NOT NULL DEFAULT 0,
	`parameterCount` int NOT NULL DEFAULT 0,
	`trainLoss` float,
	`validationLoss` float,
	`artifactPath` varchar(500),
	`isActive` boolean NOT NULL DEFAULT false,
	`createdAt` timestamp NOT NULL DEFAULT (now()),
	CONSTRAINT `modelVersions_id` PRIMARY KEY(`id`)
);
--> statement-breakpoint
CREATE INDEX `chatHistory_userId_createdAt_idx` ON `chatHistory` (`userId`,`createdAt`);--> statement-breakpoint
CREATE INDEX `modelVersions_userId_createdAt_idx` ON `modelVersions` (`userId`,`createdAt`);